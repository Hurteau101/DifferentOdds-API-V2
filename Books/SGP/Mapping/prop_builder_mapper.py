import asyncio
import time
from typing import Callable
from Books.Bases.mapper_base import MapperBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Utils.helpers import clean_structure, cache_time, decimal_to_american
import re
from curl_cffi import AsyncSession as CurlAsyncSession
import uuid

class PropBuilderMapper(MapperBase):
    def __init__(self):
        super().__init__(book_name="prop builder", category="sgp")
        self.ignore_stats = ["ppd", "specials", "all markets", "acca", "field", "h2h", "h2h", "pops"]
        self.spread_types = ["spread", "run line", "puck line", "point spread"]
        self.special_team_mapping = {
            "athletics": "oakland athletics",
        }

    @staticmethod
    async def security_token(session: CurlAsyncSession, security_url: str, api_caller: Callable):
        """
        Extracts a security token. This is required for all API calls. You must use a new one, each call
        or you will get a replay error.
        """
        token_data = await api_caller(
            session=session,
            url=security_url,
            method="POST",
            valid_codes=[201]
        )

        token = token_data.get("token")
        nonce = str(uuid.uuid4()) # Random UUID
        request_time = str(int(time.time() * 1000)) # Unix timestamp in milliseconds

        return {
            "X-Req-Challenge": token,
            "X-Req-Nonce": nonce,
            "X-Req-Time": request_time,
            "X-Req-Version": "v1"
        }

    async def _get_gfm(self, **kwargs):
        return {
            "url": f"{self.book_data.mapping.url.get('props_base')}sgmMarkets/gfm/grouped",
            "params": {
                "sb": "betus",
                "legacy": "1",
                "gameId": kwargs.get("game_id"),
            }
        }

    async def _get_exact(self, **kwargs):
        return {
            "url": f"{self.book_data.mapping.url.get('props_base')}dfm/marketsByExact",
            "params": {
                "sb": "betus",
                "statistic": kwargs.get("stat_name"),
                "gameId": kwargs.get("game_id"),
            }
        }

    async def _get_ou(self, **kwargs):
        return {
            "url": f"{self.book_data.mapping.url.get('props_base')}dfm/marketsByOu",
            "params": {
                "sb": "betus",
                "statistic": kwargs.get("stat_name"),
                "gameId": kwargs.get("game_id"),
            }
        }

    async def _get_other(self, **kwargs):
        return {
            "url": f"{self.book_data.mapping.url.get('props_base')}dfm/marketsBySs",
            "params": {
                "sb": "betus",
                "statistic": kwargs.get("stat_name"),
                "gameId": kwargs.get("game_id"),
            }
        }

    async def _get_endpoint_data(self, endpoint_key, **kwargs):
        mapper = {
            "exact": self._get_exact,
            "gfm": self._get_gfm,
            "ou": self._get_ou,
            "other": self._get_other,
        }

        return await mapper[endpoint_key](**kwargs)

    async def _run_league_market_extractor(self, session, game_ids, market_mapper, team_mapper):
        tasks = [
            self._market_extractor(
                session=session,
                game_ids=game_id_list,
                market_mapper=market_mapper,
                team_mapper=team_mapper,
                league=league,
            )
            for league, game_id_list in game_ids.items()
        ]

        return await asyncio.gather(*tasks)

    async def _market_extractor(self, session, game_ids, market_mapper, team_mapper, league):
        semaphore = asyncio.Semaphore(20)

        async def _call(url, params):
            async with semaphore:
                return await self.api_caller(
                    session=session,
                    url=url,
                    method=self.book_data.mapping.method,
                    headers={
                        **self.book_data.headers,
                        **await self.security_token(session=session, security_url=self.book_data.mapping.url.get("security_url"), api_caller=self.api_caller),
                    },
                    params=params,
                )

        tasks = []
        league_tracker = []

        for game_id in game_ids:
            for stat_type, stat_list in market_mapper[league].items():
                for stat in stat_list:
                    endpoint_data = await self._get_endpoint_data(
                        endpoint_key=stat_type, stat_name=stat, league=league, game_id=game_id
                    )
                    if not endpoint_data or "url" not in endpoint_data or "params" not in endpoint_data:
                        continue

                    tasks.append(_call(endpoint_data.get("url"), endpoint_data.get("params")))
                    league_tracker.append(league)

        response = await asyncio.gather(*tasks)

        return self._build_market_data(response=zip(league_tracker, response), team_mapper=team_mapper)

    def _clean_string(self, text):
        return re.sub(r'[-()]', '', text).strip()

    def _handle_special_game_team_mapping(self, raw_stat_name: str, current_stat_name: str, team_1_name: str, team_2_name: str):
        special_mapping = {
            "home team": f"{team_1_name}",
            "away team": f"{team_2_name}",
            "player 1": f"{team_1_name}",
            "player 2": f"{team_2_name}",
        }

        if any(special_team in raw_stat_name for special_team in special_mapping.keys()):
            for special_team, team_name in special_mapping.items():
                if special_team in raw_stat_name:
                    modify_stat_name = self._clean_string(current_stat_name.replace(special_team, '').strip())

                    # return f"{team_name}_{modify_stat_name}".lower().replace(" ", "_")
                    return team_name

        return None

    def _special_spread_mapper(self, stat_name: str, league: str):
        mapper = {
            "mlb": "run line",
            "nhl": "puck line",
            "nba": "point spread",
            "wnba": "point spread",
        }

        if "spread" in stat_name.lower():
            found_mapper = mapper.get(league)
            if found_mapper:
                return stat_name.replace("spread", found_mapper)

        return stat_name


    def _handle_game_markets(self, market: dict, mapping: dict, league: str, stat_name: str, raw_stat_name: str):
        def handle_key_name(team_1_name: str, team_2_name: str, team_1_abbrv: str, team_2_abbrv: str, g_type: dict, current_stat: str, game_line: str):
            game_type = g_type.get("type")

            if game_type in ["1", "2", "x", "none", "yes", "no"]:
                inner_mapper = {
                    "1": team_1_abbrv if any(stat in current_stat for stat in self.spread_types) else team_1_name,
                    "2": team_2_abbrv if any(stat in current_stat for stat in self.spread_types) else team_2_name,
                    # "1": team_1_name if current_stat not in self.spread_types else team_1_abbrv,
                    # "2": team_2_name if current_stat not in self.spread_types else team_2_abbrv,
                    "x": "draw",
                    "none": "none",
                    "yes": "over 0.5",
                    "no": "under 0.5",
                }


                team = inner_mapper.get(game_type)
                return [team, game_line] if game_line is not None else [team]
                # key = f"{team}_{game_line}" if line is not None else team
                # return key.lower().replace(" ", "_")


            if game_type in ["over", "under"]:
                # return f"{game_type}_{game_line}"
                return [game_type, game_line]

            return [current_stat]
            # return current_stat


        for game in market.get("markets", []):
            game_type = next((
                {
                    "type": g_type.get("type"),
                    "value": g_type.get("value"),
                    "selection": g_type.get("selection"),
                }
                for g_type in game.get("condition", [])
            ), None)

            if not game_type:
                continue

            current_stat_name = self._clean_string(stat_name)
            current_stat_name = self._special_spread_mapper(current_stat_name, league)

            game_data = game.get("game", {})
            test_game_id = game_data.get("_id")
            game_id = game.get("id")
            game_date = cache_time(game_data.get("date"))

            line = game_type.get("value")

            team_1_data = self._get_team_data("team1", game_data)
            team_2_data = self._get_team_data("team2", game_data)

            team_1_name = clean_structure(team_1_data.get("team_name", ''))
            team_1_abbrv = team_1_data.get("team_abbrv", '')
            team_2_name = clean_structure(team_2_data.get("team_name", ''))
            team_2_abbrv = team_2_data.get("team_abbrv", '')

            game_title = " vs ".join(sorted([team_1_name, team_2_name]))

            has_special_team_mapping = self._handle_special_game_team_mapping(raw_stat_name, current_stat_name, team_1_name, team_2_name)
            if has_special_team_mapping:
                current_stat_name = has_special_team_mapping


            raw_gfm_game_key = handle_key_name(team_1_name, team_2_name, team_1_abbrv, team_2_abbrv, game_type, current_stat_name, str(line))

            filtered_keys = [
                game_key
                for game_key in raw_gfm_game_key
                if game_key and game_key.lower() not in (None, '', "none")
            ]

            if current_stat_name not in filtered_keys:
                filtered_keys.append(current_stat_name)

            gfm_game_key_sorted = sorted(filtered_keys)
            gfm_game_key = "_".join(gfm_game_key_sorted).lower().replace(" ", "_")

            game_key = f"{game_title}_{game_date}".replace(" ", "_").lower()

            mapping.setdefault(game_key, {})
            mapping[game_key].setdefault(gfm_game_key, {})

            decimal_odds = game.get("odds")
            american_odds = decimal_to_american(decimal_odds)

            if american_odds:
                american_odds = int(american_odds)

            mapping[game_key][gfm_game_key].update({
                "game_id": game_id,
                "test_game_id": test_game_id,
                "statistic": raw_stat_name,
                "condition_value": line,
                "decimal_odds": decimal_odds,
                "american_odds": american_odds,
                "team_1": team_1_name,
                "team_2": team_2_name,
                "game_title": game_title,
                "game_date": game_date,
                "league": league,
            })

        return mapping

    def _handle_player_markets(self, market: dict, mapping: dict, league: str, stat_name: str, seen: set,
                               team_mapper: dict, has_ov: bool):
        base_stat_name = f"player {stat_name}"

        for player in market.get("players", []):
            player_name = player.get("name")
            player_id = player.get("id")
            for market_entry in player.get("markets", []):
                if not market_entry.get("isActive", False):
                    continue

                decimal_odds = market_entry.get("odds")
                american_odds = decimal_to_american(decimal_odds)

                if american_odds:
                    american_odds = int(american_odds)

                current_stat_name = base_stat_name

                game_1_id = market_entry.get("game1Id")
                team_data = team_mapper.get(league, {}).get(game_1_id, {})
                game_key = f"{team_data.get("game_title")}_{team_data.get("game_date")}".replace(" ", "_").lower()
                mapping.setdefault(game_key, {})

                original_line_value = market_entry.get("value")

                if has_ov:
                    direction = "over" if market_entry.get("type") == 18 else "under"
                    line = original_line_value
                else:
                    direction = "over"

                    if any(stat in current_stat_name for stat in ["first"]):
                        current_stat_name = base_stat_name.replace("player", "")
                        line = 0.5
                    else:
                        line = float(original_line_value) + 0.5

                player_key = self.build_prop_key(stat=current_stat_name, side=direction, line=str(line), player=player_name)

                mapping[game_key].setdefault(player_key, {})

                statistic_id = market_entry.get("statistic", {}).get("id")

                key = f"{player_name}_{current_stat_name}_{direction}_{line}"

                if key in seen:
                    continue

                mapping[game_key][player_key].update({
                    "player1": player_id,
                    "game1": game_1_id,
                    "player_name": player_name,
                    "statistic": statistic_id,
                    "decimal_odds": decimal_odds,
                    "american_odds": american_odds,
                    "direction": direction,
                    "condition_value": original_line_value,
                    "line": line,
                    "type": market_entry.get("type"),
                    "is_ou": has_ov,
                    "team_1": team_data.get("team_1", {}).get("team_name"),
                    "team_2": team_data.get("team_2", {}).get("team_name"),
                    "game_title": team_data.get("game_title"),
                    "game_date": team_data.get("game_date"),
                    "league": league,
                })

                seen.add(key)


    def _build_market_data(self, response: list, team_mapper: dict):
        mapping = {}
        seen = set()

        static_mapping = self.static_mapping.get("static_mapping", {})

        stat_mapping = static_mapping.get("stats", {})


        for league, data in response:
            for market in data:
                raw_stat_name = market.get("statistic", '').lower()
                stat_name = stat_mapping.get(raw_stat_name, raw_stat_name).lower()
                has_ov = market.get("type", '') == "ou"

                # Players
                if market.get("players"):

                    self._handle_player_markets(
                        market=market, mapping=mapping, league=league, stat_name=stat_name, seen=seen,
                        team_mapper=team_mapper, has_ov=has_ov
                    )
                # Games
                else:
                    self._handle_game_markets(market=market, mapping=mapping, league=league, stat_name=stat_name, raw_stat_name=raw_stat_name)

        return mapping


    async def _get_leagues(self, session: CurlAsyncSession) -> dict | list | None:
        token = await self.security_token(session=session, security_url=self.book_data.mapping.url.get("security_url"), api_caller=self.api_caller)

        return await self.api_caller(
            session=session,
            url=self.book_data.mapping.url.get("league_url"),
            method=self.book_data.mapping.method,
            headers={
                **self.book_data.headers,
                **token,
            }
        )

    async def _get_game_ids(self, session: CurlAsyncSession, league_data: dict):
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("game_url"),
                params={"league": league, "sport": sport},
                method=self.book_data.mapping.method,
                headers={
                    **self.book_data.headers,
                    **await self.security_token(session=session,
                                                security_url=self.book_data.mapping.url.get("security_url"),
                                                api_caller=self.api_caller),
                },
            )

            for league, sport in league_data.items()
        ]

        response = await asyncio.gather(*tasks)
        game_ids = {}

        for game_list in response:
            for game_data in game_list:
                if not all([game_data.get("isActive"), not game_data.get("isFinal"), ]):
                    continue

                league = game_data.get("league")
                game_ids.setdefault(league, [])

                for provider in game_data.get("providers"):
                    game_ids[league].append(provider.get("id"))


        return game_ids

    def _get_team_data(self, team_key: str, game_detail: dict):
        return next((
            {
                "team_name": self.special_team_mapping.get(team.get("title"), team.get("title")),
                "team_abbrv": team.get("abbreviation"),
            }
            for team in game_detail.get(team_key, [])
        ), None)

    async def _get_game_details(self, session: CurlAsyncSession):
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("game_details_url"),
                method=self.book_data.mapping.method,
                headers={
                    **self.book_data.headers,
                    **await self.security_token(session=session,
                                                security_url=self.book_data.mapping.url.get("security_url"),
                                                api_caller=self.api_caller),
                },
            )
        ]

        responses = await asyncio.gather(*tasks)
        game_details = {}

        for data in responses:
            for game_data in data:
                if not game_data.get("isActive", False):
                    continue

                game_id = next((
                    game_id_info.get("id")
                    for game_id_info in game_data.get("providers", [])
                ), None)

                if game_id is None:
                    continue

                league = game_data.get("league")
                game_details.setdefault(league, {})

                game_details[league].setdefault(game_id, {})

                team_1_data = self._get_team_data("team1", game_data)
                team_2_data = self._get_team_data("team2", game_data)

                team_1_name = clean_structure(team_1_data.get("team_name", ''))
                team_2_name = clean_structure(team_2_data.get("team_name", ''))

                game_title = " vs ".join(sorted([team_1_name, team_2_name]))

                game_details[league][game_id].update({
                    "team_1": team_1_data,
                    "team_2": team_2_data,
                    "game_date": cache_time(game_data.get("date")),
                    "game_title": game_title,
                })


        return game_details


    async def _market_mapper(self, session: CurlAsyncSession, league_data: dict):
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("market_url"),
                params={"league": league},
                method=self.book_data.mapping.method,
                headers={
                    **self.book_data.headers,
                    **await self.security_token(session=session,
                                                security_url=self.book_data.mapping.url.get("security_url"),
                                                api_caller=self.api_caller),
                },
            )

            for league in league_data.keys()
        ]

        responses = await asyncio.gather(*tasks)

        market_data = {}

        for league, response in zip(league_data.keys(), responses):
            # Must map these, as different groups, have different parameters when calling the endpoint.
            market_data.setdefault(league, {
                "exact": [],
                "gfm": [],
                "ou": [],
                "other": [],
            })

            for stat_name, stat_list in response.items():
                stat_name = stat_name.lower()

                if stat_name in self.ignore_stats:
                    continue

                for stat in stat_list:

                    if re.search(r"\(exact\)", stat.lower()):
                        stat = re.sub(r"\s*\(exact\)\s*", " ", stat, flags=re.IGNORECASE).strip()
                        market_data[league]["exact"].append(stat)
                        continue

                    if stat_name in market_data[league].keys():
                        market_data[league][stat_name].append(stat)
                        continue

                    market_data[league]["other"].append(stat)

        return market_data

    async def run_mapper(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            raw_leagues = await self._get_leagues(session=session)

            leagues = {
                league.get("name"): league.get("sport")
                for league in raw_leagues
            }

            game_ids = await self._get_game_ids(session=session, league_data=leagues)
            game_details = await self._get_game_details(session=session)
            market_mapper = await self._market_mapper(session=session, league_data=leagues)

            mapped_ids = await self._run_league_market_extractor(
                session=session,
                game_ids=game_ids,
                market_mapper=market_mapper,
                team_mapper=game_details,
            )

            mapped_ids = {
                key: value
                for data in mapped_ids
                for key, value in data.items()
            }

            if not mapped_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No mapping found"
                )
                return False

            await self.store_data(
                key_name=self.mapper_id_name,
                data_to_store=mapped_ids,
                expiration_time=self.pre_calculated_redis_expiration
            )

            return True

if __name__ == "__main__":
    prop_builder = PropBuilderMapper()
    asyncio.run(prop_builder.run_mapper())
