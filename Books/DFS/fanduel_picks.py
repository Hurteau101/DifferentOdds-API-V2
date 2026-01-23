import asyncio
import re
import aiohttp
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Books.Bases.dfs_book_base import DFSBookBase
from Settings.Models.dfs_models import GameData, TeamData, Stats, OptionalStatInformation
from Utils.request_caller import SportbookRequestType


class FanDuelPicks(DFSBookBase):
    VALID_LEAGUES = ["NFL", "MLB", "NHL", "NBA", "NCAAF"]

    def __init__(self):
        super().__init__(book_name="fanduel_picks", request_type=SportbookRequestType.ASYNC)

    def _extract_league(self, player_image_source: str, team_image_source: str) -> str | None:
        """
        Extracts league from FanDuel image URLs.
        Supports both team and player image formats.
        """
        patterns = [
            r"/team/([^/]+)/",
            r"/playerimages/([^/]+)/",
        ]

        for src in (player_image_source, team_image_source):
            if not src:
                continue

            for pattern in patterns:
                match = re.search(pattern, src, re.IGNORECASE)
                if match:
                    return match.group(1).lower()

        return None

    def _extract_data(self, raw_data: dict) -> GameData | None:
        player_data = raw_data.get("prop").get("competitor", {})
        team_data = raw_data.get("prop").get("fixture")
        first_name = player_data.get("firstNames", "")
        last_name = player_data.get("lastName", "")
        player_team = player_data.get("team", {}).get("name")
        start_date = team_data.get("startsAt")
        team_a = team_data.get("homeTeam", {}).get("name")
        team_a_abbreviation = team_data.get("homeTeam", {}).get("abbreviation", "")
        team_b = team_data.get("awayTeam", {}).get("name")
        team_b_abbreviation = team_data.get("awayTeam", {}).get("abbreviation", "")
        stat_type = raw_data.get("gameGroupMarket", {}).get("displayName").lower()

        player_image_source = player_data.get("imageSrc", "")
        team_image_source = team_data.get("homeTeam", {}).get("imageSrc", "") or team_data.get("awayTeam", {}).get("imageSrc", "")
        league = self._extract_league(player_image_source, team_image_source)

        if not league:
            create_sentry_message(
                tag_key="league_mapper",
                tag_value="".join(raw_data),
                message="Can't find league data",
                level="error"
            )

            return None

        if team_a and team_b:
            team_key = FanDuelPicks.generate_key([team_a, team_b, start_date])
        else:
            team_key = FanDuelPicks.generate_key([f"{first_name} {last_name}", start_date])

        over_under_mapper = {
            "MORE": "over",
            "LESS": "under"
        }

        return GameData(
            league=league.lower(),
            start_date=start_date,
            game_key=team_key,
            team_data=TeamData(
                team_a=team_a,
                team_a_abbreviation=team_a_abbreviation,
                team_b=team_b,
                team_b_abbreviation=team_b_abbreviation,
            ),
            future=False,
            odds=[
                Stats(
                    player_name=f"{first_name} {last_name}",
                    player_team=player_team,
                    stat_type=stat_type.lower(),
                    line=raw_data.get("line"),
                    bet_type=over_under_mapper.get(direction.get("selection", {}).get("type"), "N/A"),
                    regular_line=True if direction.get("oddsRangeType") == "REGULAR" else False,
                    optional_stats=OptionalStatInformation(
                        odds_type="Standard" if direction.get("oddsRangeType") == "REGULAR" else "Spicy",
                        internal_id=direction.get("id")
                    ),
                )
                for direction in raw_data.get("gameGroupSelections", [])
            ],
            solo_game=False
        )

    def extract_game_id(self, lobby_data):
        id_pattern = re.compile(
            r"\b[0-9a-f]+(?:-[0-9a-f]+){2,}\b",
            re.IGNORECASE
        )

        return list(set(id_pattern.findall(str(lobby_data))))

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            redis_instance = RedisAsyncManager(database=5)
            auth_token = await redis_instance.get_data("fanduel_picks_auth_token")

            if not auth_token:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="auth_failure",
                    message="Couldn't retrieve Fanduel Picks access token from Redis.",
                    level="error"
                )
                return

            headers = self.book_data.headers

            headers.update({
                "Cookie": f"X-Auth-Token={auth_token}"
            })

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("main_url").format(league=league),
                    method=self.book_data.method,
                    headers=headers,
                )
                for league in FanDuelPicks.VALID_LEAGUES
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="Main API URL returned no data",
                    level="error"
                )

                return

            results = [result for result in results if result]
            game_ids = self.extract_game_id(results)

            stat_tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("stat_url").format(game_id=game),
                    method=self.book_data.method,
                    headers=headers
                )
                for game in game_ids
            ]

            results = await asyncio.gather(*stat_tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No stats data returned",
                    level="error"
                )

                return

            merge_data = [
                {
                    "game_id": game,
                    "data": resp
                }
                for game, resp in zip(game_ids, results)
            ]

            events = {}

            for sports_data in merge_data:
                for game_details in sports_data.get("data").get("gameGroupProps", []):
                    if len(sports_data.get("data").get("gameGroupProps", [])) == 0:
                        continue

                    player_data = self._extract_data(game_details)
                    if player_data:
                        self.add_to_events(events, player_data, GameData)

            fanduel_picks_data = list(events.values())

            mapped_data = await self.external_mapper(fanduel_picks_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data