import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import GameData, TeamData, Stats
from Utils.request_caller import SportbookRequestType
from datetime import datetime

class SplashSports(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="splashsports", request_type=SportbookRequestType.ASYNC)

    def _extract_game_data(self, game_data: dict) -> GameData | None:
        if not game_data:
            return None

        start_date = game_data.get("game_start")
        start_date = datetime.fromtimestamp(start_date / 1000).isoformat()

        player_name = game_data.get("entity").get("name")
        player_team = game_data.get("team", {}).get("alias")
        team_a = game_data.get("game", {}).get("home", {}).get("alias")
        team_b = game_data.get("game", {}).get("away", {}).get("alias")

        if team_a and team_b:
            team_key = SplashSports.generate_key([team_a, team_b, start_date])
        else:
            team_key = SplashSports.generate_key([player_name, start_date])

        return GameData(
            league=game_data.get("league").lower(),
            game_key=team_key,
            start_date=start_date,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
            ),
            future=False,
            odds=[
                Stats(
                    player_name=player_name,
                    player_team=player_team,
                    stat_type=game_data.get("type_display"),
                    line=game_data.get("line"),
                    bet_type=option,
                    regular_line=True
                )

                for option in ["over", "under"]
            ],
            solo_game=False if all([team_a, team_b]) else True
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
            )

            if not api_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="Main API URL returned no data",
                    level="error"
                )
                return

            events = {}

            for game_details in api_data.get("data"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            game_data = list(events.values())

            mapped_data = await self.external_mapper(game_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data