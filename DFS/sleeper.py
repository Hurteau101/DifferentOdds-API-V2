from datetime import datetime
import asyncio
import aiohttp

from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation


class Sleeper(DFSBookBase):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC, sportsbook_name="sleeper")

    @staticmethod
    def _map_games(games):
        return {game["game_id"]: game for game in games if game.get("status") == "pre_game"}

    @staticmethod
    def _map_players(players):
        return {f"{player['player_id']}-{player['sport']}": player for player in players}

    def _extract_game_data(self, game_data, team_data, player_information):
        def configure_stats(stat_type):
            stat_type = stat_type.replace("_", " ").lower()
            return STAT_TYPES.get(stat_type, stat_type).title()

        if not game_data or not team_data or not player_information:
            return None

        player_details = player_information.get(f"{game_data['subject_id']}-{game_data['sport']}")

        team_information = team_data.get(game_data["game_id"])

        if not player_details or not team_information:
            return None

        player_name = player_details.get("username") if player_details.get("username") else f"{player_details.get('first_name')} {player_details.get('last_name')}"
        player_name = self.clean_and_normalize_name(player_name)

        # Games are sometimes missing team data, so we need to handle both cases.
        if not isinstance(team_information.get("metadata", {}).get("home_team"), dict):
            team_a = team_information.get("metadata", {}).get("home_team")
            team_b = team_information.get("metadata", {}).get("away_team")
        else:
            team_a = team_information.get("metadata").get("home_team").get("team")
            team_b = team_information.get("metadata").get("away_team").get("team")

        player_team = self.clean_and_normalize_name(player_details.get("subject_team"))
        start_date = self.cache_time(datetime.fromtimestamp(team_information.get('start_time') / 1000).isoformat())

        team_a = self.clean_and_normalize_name(team_a)
        team_b = self.clean_and_normalize_name(team_b)

        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([player_name, start_date])

        league = game_data.get("sport")

        # If it's a season long prop, the sport is 'custom'. We need to get the actual sport from custom_sport field.
        if league == "custom":
            league = game_data.get("custom_sport").replace("_", " ")

        league = LEAGUES.get(league.lower(), league.upper())

        return PlayerData(
            player_name=player_name,
            league=league,
            start_date=start_date,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
                player_team=player_team,
                team_key=team_key,
            ),
            future=True if "szn" in league.lower() else False,
            solo_game=False if all([team_a, team_b]) else True,
            stats=[
                Stats(
                    stat_type=configure_stats(option.get("wager_type")),
                    line=option.get("outcome_value"),
                    bet_direction=option.get("outcome"),
                    regular_line=True if float(option.get("payout_multiplier")) == 1.00 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=float(option.get("payout_multiplier"))
                    )
                )
                for option in game_data.get("options", [])
            ]
        )

    def extract_data(self, response):
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return response

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(session=session, url=self.book_data.url.get("main_url"),method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url"),method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_2"), method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_3"),method=self.book_data.method),
                self.api_caller(session=session, url=self.book_data.url.get("alternate_url_4"),method=self.book_data.method),
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
                checked = self.check_api_response("sleeper", data)
                if checked is None:
                    checked = []

                responses[name] = checked

            main_lines = responses["main_line"]
            alternate_lines = responses["alternate_line"]
            game_data = responses["game_data"]
            player_data = responses["player_data"]
            season_data = responses["season_data"]

            combined_lines = self.extract_data(main_lines) + self.extract_data(alternate_lines)
            combined_game_data = self.extract_data(game_data) + self.extract_data(season_data)
            team_data = self._map_games(combined_game_data)
            player_information = self._map_players(self.extract_data(player_data))

            player_data_list = {}
            for game_details in combined_lines:
                if game_details.get('status') == "active": # Ensure it's an active game.
                    player_data = self._extract_game_data(game_details, team_data, player_information)
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

            sleeper_data = list(player_data_list.values())
            return await self._database_mapper(sleeper_data)


if __name__ == "__main__":
    sleeper = Sleeper()
    import asyncio
    asyncio.run(sleeper.run_book())
