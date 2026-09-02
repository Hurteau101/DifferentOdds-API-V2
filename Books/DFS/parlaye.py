from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.dfs_base import DFSBookBase
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from curl_cffi import AsyncSession as CurlAsyncSession


class Parlaye(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="parlaye")

    def _extract_game_data(self, game_data: dict) -> GameData:
        player_name = f"{game_data.get('player_first_name')} {game_data.get('player_last_name')}"
        team_a = game_data.get("team")
        team_b = game_data.get("opposing_team")
        start_date = game_data.get("game_start_time")

        if team_a and team_b:
            team_key = Parlaye.generate_key([team_a, team_b, start_date])
        else:
            team_key = Parlaye.generate_key([player_name, start_date])

        odds_mapper = {
            "over": {
                "american_odds": game_data.get("moneyline_more"),
                "points": game_data.get("points_more"),
            },
            "under": {
                "american_odds": game_data.get("moneyline_less"),
                "points": game_data.get("points_less"),
            }
        }

        return GameData(
            league=game_data.get("league"),
            game_key=team_key,
            start_date=start_date,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
            ),
            odds=[
                DFSStats(
                    static_mapping=self.static_mapping,
                    player_name=player_name,
                    player_team=team_a,
                    stat_type=game_data.get("pick_type"),
                    line=float(game_data.get("pick_number")),
                    bet_type=option,
                    future=False,
                    regular_line=True,
                    odds_format=OddsFormat(
                        american_odds=float(odds_mapper.get(option).get("american_odds")),
                        points=odds_mapper.get(option).get("points")
                    )
                )
                for option in ["over", "under"]
            ],
            solo_game=True if not all([team_a, team_b]) else False
        )


    async def run_book(self) -> list | None:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                json={"id_player": "1"},
            )

            if not api_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.API_NO_DATA,
                    error_message="No API data found"
                )
                return None

            events = {}

            for game_details in api_data.get("picks"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            parlaye_data = list(events.values())

            if not parlaye_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.NO_EXTRACTION_DATA,
                    error_message="No event data found"
                )
                return None

            await self.store_data(
                data_to_store=parlaye_data,
                key_name=self.book_data.name
            )

            return parlaye_data

if __name__ == "__main__":
    import asyncio
    parlaye = Parlaye()
    asyncio.run(parlaye.run_book())