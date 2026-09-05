import asyncio
from datetime import datetime
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.dfs_base import DFSBookBase
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData
from curl_cffi import AsyncSession as CurlAsyncSession


class Sleeper(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="sleeper")

    @staticmethod
    def _map_games(games: list) -> dict:
        return {game["game_id"]: game for game in games if game.get("status") == "pre_game"}

    @staticmethod
    def _map_players(players: list) -> dict:
        return {f"{player['player_id']}-{player['sport']}": player for player in players}

    def _extract_game_data(self, game_data: dict, team_data: dict, player_information: dict) -> GameData | None:
        def configure_stats(stat_type):
            stat_type = stat_type.replace("_", " ").lower()
            return stat_type

        if not game_data or not team_data or not player_information:
            return None

        player_details = player_information.get(f"{game_data['subject_id']}-{game_data['sport']}")

        team_information = team_data.get(game_data["game_id"])

        if not player_details or not team_information:
            return None

        player_name = player_details.get("username") if player_details.get(
            "username") else f"{player_details.get('first_name')} {player_details.get('last_name')}"

        # Games are sometimes missing team data, so we need to handle both cases.
        if not isinstance(team_information.get("metadata", {}).get("home_team"), dict):
            team_a = team_information.get("metadata", {}).get("home_team")
            team_b = team_information.get("metadata", {}).get("away_team")
        else:
            team_a = team_information.get("metadata").get("home_team").get("team")
            team_b = team_information.get("metadata").get("away_team").get("team")

        player_team = player_details.get("team")
        start_date = datetime.fromtimestamp(team_information.get('start_time') / 1000).isoformat()

        if team_a and team_b:
            team_key = Sleeper.generate_key([team_a, team_b, start_date])
        else:

            team_key = Sleeper.generate_key([player_name, start_date])

        league = game_data.get("sport")

        # If it's a season long prop, the sport is 'custom'. We need to get the actual sport from custom_sport field.
        if league == "custom":
            league = game_data.get("custom_sport").replace("_", " ")

        return GameData(
            league=league,
            game_key=team_key,
            start_date=start_date,
            team_a=team_a,
            team_b=team_b,
            solo_game=False if all([team_a, team_b]) else True,
            odds=[
                DFSStats(
                    league=league,
                    player_name=player_name,
                    player_team=player_team,
                    future=True if "szn" in league.lower() else False,
                    stat_type=configure_stats(option.get("wager_type")),
                    line=option.get("outcome_value"),
                    bet_type=option.get("outcome"),
                    regular_line=True if float(option.get("payout_multiplier")) == 1.00 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=float(option.get("payout_multiplier"))
                    )
                )
                for option in game_data.get("options", [])
            ]
        )

    def extract_data(self, response: dict) -> list | dict:
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return response

    async def run_book(self) -> list | None:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            tasks = [
                self.api_caller(session=session, url=self.book_data.url.get("main_url"), method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url"),
                                method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_2"),
                                method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_3"),
                                method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_4"),
                                method=self.book_data.method),
            ]

            main_lines, alternate_lines, game_data, player_data, season_data = await asyncio.gather(*tasks)

            responses = {
                "main_line": main_lines,
                "alternate_line": alternate_lines,
                "game_data": game_data,
                "player_data": player_data,
                "season_data": season_data,
            }

            for name, data in responses.items():
                responses[name] = data if data is not None else []

            main_lines = responses["main_line"]
            alternate_lines = responses["alternate_line"]
            game_data = responses["game_data"]
            player_data = responses["player_data"]
            season_data = responses["season_data"]

            combined_lines = self.extract_data(main_lines) + self.extract_data(alternate_lines)

            if not combined_lines:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.API_NO_DATA,
                    error_message="No API data found"
                )
                return None

            combined_game_data = self.extract_data(game_data) + self.extract_data(season_data)
            team_data = self._map_games(combined_game_data)
            player_information = self._map_players(self.extract_data(player_data))

            events = {}
            for game_details in combined_lines:
                if game_details.get('status') == "active":  # Ensure it's an active game.
                    player_data = self._extract_game_data(game_details, team_data, player_information)
                    if player_data:
                        self.add_to_events(events, player_data, GameData)


            sleeper_data = list(events.values())

            if not sleeper_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.NO_EXTRACTION_DATA,
                    error_message="No event data found"
                )
                return None

            await self.store_data(
                data_to_store=sleeper_data,
                key_name=self.book_data.name
            )

            await self.flush_unmapped()
            return sleeper_data

if __name__ == "__main__":
    sleeper = Sleeper()
    asyncio.run(sleeper.run_book())