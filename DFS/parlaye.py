import aiohttp
import asyncio
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation, Odds
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.book_base import SportbookRequestType

class Parlaye(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="parlaye")


    def _extract_game_data(self, game_data):
        player_name = f"{game_data.get('player_first_name')} {game_data.get('player_last_name')}"
        team_a = game_data.get("team")
        team_b = game_data.get("opposing_team")
        start_date = self.cache_time(game_data.get("game_start_time"))

        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([player_name, start_date])

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

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_name),
            league=LEAGUES.get(game_data.get("league").lower(), game_data.get("league").upper()),
            start_date=start_date,
            team_data=TeamData(
                team_a=self.clean_and_normalize_name(team_a),
                team_b=self.clean_and_normalize_name(team_b),
                team_key=team_key,
                player_team=self.clean_and_normalize_name(team_a),
            ),
            future=False,
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(game_data.get("pick_type").lower(), game_data.get("pick_type")).title(),
                    line=float(game_data.get("pick_number")),
                    bet_direction=option,
                    regular_line=True,
                    optional_stats=OptionalStatInformation(
                        odds=Odds(
                            american_odds=float(odds_mapper.get(option).get("american_odds")),
                            points=odds_mapper.get(option).get("points")
                        )

                    )
                )
                for option in ["over", "under"]
            ],
            solo_game=True if not all([team_a, team_b]) and self.solo_checker(LEAGUES.get(game_data.get("league").lower(), game_data.get("league").upper())) else False
        )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                payload={"id_player": "1"},
            )

            api_data = self.check_api_response(sportsbook="parlaye", results=raw_api_data)

            if not api_data:
                return

            player_data_list = {}

            for game_details in api_data.get("picks"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    player_key = (
                        player_data.player_name,
                        player_data.team_data.team_a,
                        player_data.team_data.team_b,
                        player_data.start_date,
                    )

                    if player_key in player_data_list:
                        player_data_list[player_key].stats.extend(player_data.stats)
                    else:
                        player_data_list[player_key] = player_data

            parlaye_data = list(player_data_list.values())
            return await self._database_mapper(parlaye_data)


if __name__ == "__main__":
    parlay = Parlaye()
    asyncio.run(parlay.run_book())