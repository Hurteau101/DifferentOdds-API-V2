import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import GameData, TeamData, Stats, OptionalStatInformation, OddsFormat
from Utils.request_caller import SportbookRequestType


class Parlaye(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="parlaye", request_type=SportbookRequestType.ASYNC)

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
            future=False,
            odds=[
                Stats(
                    player_name=player_name,
                    player_team=team_a,
                    stat_type=game_data.get("pick_type"),
                    line=float(game_data.get("pick_number")),
                    bet_type=option,
                    regular_line=True,
                    optional_stats=OptionalStatInformation(
                        odds_format=OddsFormat(
                            american_odds=float(odds_mapper.get(option).get("american_odds")),
                            points=odds_mapper.get(option).get("points")
                        )

                    )
                )
                for option in ["over", "under"]
            ],
            solo_game=True if not all([team_a, team_b]) else False
        )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                payload={"id_player": "1"},
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

            for game_details in api_data.get("picks"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            parlaye_data = list(events.values())

            mapped_data = await self.external_mapper(parlaye_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data