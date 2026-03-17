import asyncio
import json
import os
from itertools import zip_longest, batched
import aiohttp
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager, RedisSyncManager, static_mapping_service
from Utils.request_caller import APICaller, SportbookRequestType


class BettoroddsMapping(APICaller):
    def __init__(self, payload_batch: int, async_batch: int, book_name: str):
        self.payload_batch = payload_batch # Used for batching the payload.
        self.async_batch = async_batch # Used for BettorOdds API batching
        self.book_name = book_name
        self.redis_instance = RedisAsyncManager(database=4)
        self.league_mapping = static_mapping_service.get().get("leagues", {})
        super().__init__(request_type=SportbookRequestType.ASYNC)



    def _map_teams_players(self, data: dict, collection_key: str, league: str) -> dict:
        """Maps the leagues and players from BettorOdds API"""
        mapped = {
            "mapped": {},
            "unmapped": {}
        }

        for key, value in data.items():
            if not value:
                mapped["unmapped"][key] = league
                continue

            original = value.get("query")

            if not original:
                mapped["unmapped"][key] = league

            found = next(
                (
                    item
                    for item in value.get(collection_key, [])
                    if item.get("league").lower() == league.lower() or item.get("sport").lower() == league.lower()
                ),
                None,
            )

            if found:
                mapped["mapped"][f"{original}-{league}".lower()] = {
                    **(
                        {"team_name": found.get("normalized_name")} if collection_key == "teams"
                        else {"player_name": found.get("normalized_name")}
                    ),
                    "league": found.get("league"),
                    "original_league": league.upper(),
                    "original_name": original.lower(),
                    "source": "External"
                }
            else:
                mapped["unmapped"][original] = league

        return mapped

    def _map_markets(self, data: dict, league: str) -> dict:
        """Maps the markets from BettorOdds API"""

        mapped = {
            "mapped": {},
            "unmapped": {}
        }

        league_upper = league.upper()
        league_lower = league.lower()

        sport = self.league_mapping.get(league_upper, {}).get("sport")
        sport_lower = sport.lower() if sport else None

        for value in data.values():
            if not value:
                continue

            original = value.get("query")
            normalized = value.get("normalized_name")
            match_list = value.get("matches", [])

            if match_list and sport_lower:
                normalized = next(
                    (
                        match.get("normalized_name")
                        for match in match_list
                        if any(s.lower() == sport_lower for s in match.get("sports", []))
                    ),
                    normalized
                )

                print("Normalized Found", normalized)

            if original and normalized:
                mapped["mapped"][f"{original.lower()}-{league_lower}"] = normalized
            elif original:
                mapped["unmapped"][original] = league

        return mapped

    def map_bettorodds(self, bettorodds_data: dict, league: str):
        """Map the bettorodds data and return it in a standard formulized dictionary."""
        if not bettorodds_data:
            return {}

        players = bettorodds_data.get("player", {})
        teams = bettorodds_data.get("team", {})
        market = bettorodds_data.get("market", {})

        return {
            "teams": self._map_teams_players(data=teams, collection_key="teams", league=league),
            "players": self._map_teams_players(data=players, collection_key="players", league=league),
            "markets": self._map_markets(data=market, league=league),
        }

    async def build_payload(self, sportsbook_data: list) -> dict:
        def create_key(raw_name: str, league: str):
            return f"{raw_name.lower().strip()}-{league.lower().strip()}"

        mapping_dict = {}

        for data in sportsbook_data:
            league = data.league

            mapping_dict.setdefault(
                league,
                {
                    "teams": set(),
                    "players": set(),
                    "markets": set(),
                }
            )

            for team in (data.team_data.team_a, data.team_data.team_b):
                if team and not await self.redis_instance.is_seen("seen_teams", create_key(team, league)):
                    mapping_dict[league]["teams"].add(team)

            for odds in data.odds:
                player_name = getattr(odds, "player_name", None) or getattr(odds, "bet_player", None)
                stat_type = getattr(odds, "stat_type", None) or getattr(odds, "market", None)


                if player_name and not await self.redis_instance.is_seen(
                        "seen_players", create_key(player_name, league)
                ):
                    mapping_dict[league]["players"].add(player_name)

                if stat_type and not await self.redis_instance.is_seen(
                        "seen_markets", create_key(stat_type, league)
                ):
                    mapping_dict[league]["markets"].add(stat_type)

        batched_data = {
            league: {
                k: list(batched(v, self.payload_batch))
                for k, v in league_data.items()
            }
            for league, league_data in mapping_dict.items()
        }

        return {
            league: [
                {
                    "team": list(teams) or [],
                    "player": list(players) or [],
                    "market": list(markets) or [],
                }
                for teams, players, markets in zip_longest(
                    league_data.get("teams", []),
                    league_data.get("players", []),
                    league_data.get("markets", []),
                    fillvalue=[]
                )
            ]
            for league, league_data in batched_data.items()
        }

    async def bettorodds_api_caller(self, session: aiohttp.ClientSession, payload: dict, league: str):
        if not payload:
            return None

        api_key = os.getenv("INTERNAL_BETTORODDS_MAPPER_API_KEY")

        if not api_key:
            create_sentry_message(
                tag_key="BettorOdds Mapper",
                tag_value="api_failure",
                message="No API key provided.",
                level="error"
            )

            return None

        api_data = await self.api_caller(
            book_name=self.book_name,
            session=session,
            url="https://cache-api.eternitylabs.co/cache/batch",
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            payload=payload
        )

        return self.map_bettorodds(bettorodds_data=api_data, league=league)

    async def run_mapping(self, sportsbook_data: list, session: aiohttp.ClientSession) -> dict:
        if not sportsbook_data:
            return {}

        previously_stored = {
            name: await self.redis_instance.get_hset(name)
            for name in ["players", "markets", "teams"]
        }

        # print(f'''
        # - Previous Team Length: {len(previously_stored.get("teams"))}\n
        # - Previous Player Length: {len(previously_stored.get("players"))}\n
        # - Previous Market Length: {len(previously_stored.get("markets"))}\n\n
        # ''')

        payload_batch = await self.build_payload(sportsbook_data=sportsbook_data)

        for league, league_data in payload_batch.items():
            teams = set()
            players = set()
            markets = set()

            for item in league_data:
                teams.update(item["team"])
                players.update(item["player"])
                markets.update(item["market"])

            await self.redis_instance.add_seen(
                "seen_teams",
                [f"{t.strip().lower()}-{league.lower()}" for t in teams],
            )

            await self.redis_instance.add_seen(
                "seen_players",
                [f"{p.strip().lower()}-{league.lower()}" for p in players],
            )

            await self.redis_instance.add_seen(
                "seen_markets",
                [f"{m.strip().lower()}-{league.lower()}" for m in markets],
            )

        results = []

        for league, league_data in payload_batch.items():
            for i in range(0, len(league_data), self.async_batch):
                # print(f"Running Mapping [{league}] {i}")
                batch = league_data[i: i + self.async_batch]
                print(f"Processing {league} batch {i} to {i + self.async_batch}")
                print(batch)
                tasks = [
                    self.bettorodds_api_caller(
                        session=session,
                        payload=payload,
                        league=league
                    )
                    for payload in batch
                ]

                results.extend(await asyncio.gather(*tasks))

        breakdown_results = {
            side: {
                category: {
                    k: v
                    for result in results
                    for k, v in result.get(category, {}).get(side, {}).items()
                }
                for category in ("teams", "players", "markets")
            }
            for side in ("mapped", "unmapped")
        }

        categories = ("teams", "players", "markets")

        for category in categories:
            mapped = breakdown_results["mapped"][category]

            await self.redis_instance.store_mappings(
                f"{category}",
                mapped
            )

        final_results = {
            category: {
                **previously_stored.get(category, {}),
                **breakdown_results["mapped"].get(category, {})
            }
            for category in ("teams", "players", "markets")
        }

        # print(final_results)
        # return final_results
        # return breakdown_results.get("mapped", {})

        return final_results






