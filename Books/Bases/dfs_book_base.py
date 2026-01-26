from collections import defaultdict

from Books.Bases.book_base import BookBase
from Utils.request_caller import SportbookRequestType
from Settings.Models.dfs_models import GameData, Stats


class DFSBookBase(BookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="DFS", book_name=book_name, request_type=request_type, expiration_time=600, redis_database=0)
        self.esport_leagues = ["LOL", "CS2", "DOTA2", "VAL", "COD", "APEX", "R6"]

    def solo_mapper(self, stats: Stats, game_data: GameData, mapped_teams: dict):
        """Maps the player's name in the game data if it matches a solo game."""
        found_team = mapped_teams.get(stats.player_name.lower())
        if found_team:
            game_data.league = found_team["league"]
            game_data.player_team = found_team["team_name"]
            self.generate_key([stats.player_name, game_data.start_date])

    def player_team_mapper(self, stats: Stats, mapped_teams: dict):
        """Maps the player's team name in the game data if it matches the original team name."""
        player_team = stats.player_team

        if player_team and player_team.lower() == mapped_teams["original_name"].lower():
            stats.player_team = mapped_teams["team_name"]

    def yield_game_data(self, book_data):
        """Helper function to yield game data from nested lists. Must follow specific structure of list of lists.
        With no inner function call to extract data"""
        for game in book_data:
            for game_data in game:
                if game_data:
                    yield game_data


    async def builder_test(self, sportsbook_data: list):
        data = {
            "teams": set(),
            "players": set(),
        }

        for d in sportsbook_data:

            data["teams"].add(d.team_data.team_a)
            data["teams"].add(d.team_data.team_b)

            for odds in d.odds:
                data["players"].add(odds.player_name)

        result = {
            "teams": list(data["teams"]),
            "players": list(data["players"]),
        }

        import json
        print(json.dumps(result["teams"][0:50]))
        print()
        print(len(result["teams"][0:50]))

        # passer = [
        #     {
        #         "team": [
        #             team
        #             for team in (data.team_data.team_a, data.team_data.team_b)
        #         ]
        #     }
        #
        #
        #     for data in sportsbook_data
        #     for odds in data.odds
        # ]


        # raw_unique_data_passer = [
        #     {
        #         "player_name": odds.player_name,
        #         "team_a": data.team_data.team_a,
        #         "team_b": data.team_data.team_b,
        #     }
        #
        #     for data in sportsbook_data
        #     for odds in data.odds
        # ]
        #
        # print(raw_unique_data_passer)


    async def external_mapper(self, sportsbook_data: list):
        """Maps the sportsbook data using external mappings."""
        raw_unique_data_passer = [
            {
                "player_name": odds.player_name,
                "league": data.league,
                "combo": odds.combo,
                "solo_game": data.solo_game,
                "future": data.future,
                "team_a": data.team_data.team_a,
                "team_b": data.team_data.team_b,
            }

            for data in sportsbook_data
            for odds in data.odds
        ]

        sportsbook_name = self.__class__.__name__
        teams_mapped = await self.team_look_up(raw_unique_data=raw_unique_data_passer, sportsbook_name=sportsbook_name)

        mapped_data = self.map_helper(
            sportsbook_data=sportsbook_data,
            mapped_teams=teams_mapped,
            solo_game_mapper_func=self.solo_mapper,
            player_team_mapper_func=self.player_team_mapper,
        )

        return mapped_data







