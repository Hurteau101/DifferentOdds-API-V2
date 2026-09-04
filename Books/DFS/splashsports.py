from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.dfs_base import DFSBookBase
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData
from datetime import datetime
from curl_cffi import AsyncSession as CurlAsyncSession

class SplashSports(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="splashsports")

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
            team_a=team_a,
            team_b=team_b,
            odds=[
                DFSStats(
                    league=game_data.get("league").lower(),
                    player_name=player_name,
                    player_team=player_team,
                    future=False,
                    stat_type=game_data.get("type_display"),
                    line=game_data.get("line"),
                    bet_type=option,
                    regular_line=True
                )

                for option in ["over", "under"]
            ],
            solo_game=False if all([team_a, team_b]) else True
        )

    async def run_book(self) -> list | None:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
            )

            if not api_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.API_NO_DATA,
                    error_message="No API data found"
                )
                return None

            events = {}

            for game_details in api_data.get("data"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            game_data = list(events.values())

            if not game_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.NO_EXTRACTION_DATA,
                    error_message="No event data found"
                )
                return None

            await self.store_data(
                data_to_store=game_data,
                key_name=self.book_data.name
            )

            await self.flush_unmapped()
            return game_data

if __name__ == "__main__":
    import asyncio
    splash = SplashSports()
    asyncio.run(splash.run_book())