from datetime import datetime
import asyncio
import aiohttp
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import Stats, PlayerData, TeamData
from Settings.book_base import SportbookRequestType

class SplashSports(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="splashsports")


    def _extract_game_data(self, game_data):
        if not game_data:
            return None

        start_date = game_data.get("game_start")
        start_date = self.cache_time(datetime.fromtimestamp(start_date / 1000).isoformat())

        player_name = game_data.get("entity").get("name")
        player_team = game_data.get("team", {}).get("alias")
        team_a = game_data.get("game", {}).get("home", {}).get("alias")
        team_b = game_data.get("game", {}).get("away", {}).get("alias")

        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([player_name, start_date])

        return PlayerData(
            player_name=player_name,
            league=LEAGUES.get(game_data.get("league").lower(), game_data.get("league").upper()),
            start_date=start_date,
            team_data=TeamData(
                team_a=self.clean_and_normalize_name(team_a),
                team_b=self.clean_and_normalize_name(team_b),
                team_key=team_key,
                player_team=self.clean_and_normalize_name(player_team),
            ),
            future=False,
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(game_data.get("type_display").lower(), game_data.get("type_display")).title(),
                    line=game_data.get("line"),
                    bet_direction=option,
                    regular_line=True
                )

                for option in ["over", "under"]
            ],
            solo_game=False if all([team_a, team_b]) else True
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
            )

            api_data = self.check_api_response(sportsbook="splashsports", results=raw_api_data)

            if not api_data:
                return

            game_data = {}

            for game_details in api_data.get("data"):
                player_data = self._extract_game_data(game_details)
                if player_data:
                    player_key = (
                        player_data.player_name,
                        player_data.team_data.team_a,
                        player_data.team_data.team_b,
                        player_data.start_date,
                    )

                    if player_key in game_data:
                        game_data[player_key].stats.extend(player_data.stats)
                    else:
                        game_data[player_key] = player_data

            game_data = list(game_data.values())
            return await self._database_mapper(game_data)


if __name__ == "__main__":
    splash_sports = SplashSports()
    asyncio.run(splash_sports.run_book())