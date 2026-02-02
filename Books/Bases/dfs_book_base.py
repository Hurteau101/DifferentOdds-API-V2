import os
import aiohttp
from dotenv import load_dotenv
from Books.Bases.book_base import BookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData
from itertools import batched, zip_longest

class DFSBookBase(BookBase):
    load_dotenv()
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="DFS", book_name=book_name, request_type=request_type, redis_database=0)
        self.esport_leagues = ["LOL", "CS2", "DOTA2", "VAL", "COD", "APEX", "R6"]

    def solo_mapper(self, stats: DFSStats, game_data: GameData, mapped_teams: dict):
        """Maps the player's name in the game data if it matches a solo game."""
        found_team = mapped_teams.get(stats.player_name.lower())
        if found_team:
            game_data.league = found_team["league"]
            game_data.player_team = found_team["team_name"]
            self.generate_key([stats.player_name, game_data.start_date])

    def player_team_mapper(self, stats: DFSStats, mapped_teams: dict):
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

    async def bettor_odds_external_caller(self, session: aiohttp.ClientSession, payload: dict, league: str):
        if not payload:
            return None

        api_key = os.getenv("INTERNAL_BETTORODDS_MAPPER_API_KEY")

        if not api_key:
            create_sentry_message(
                tag_key="BettorOdds Mapper",
                tag_value="api_failure",
                message="No API key provided.",
                level="error"
            )

            return None

        import time
        start_time = time.perf_counter()
        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url="https://cache-api.eternitylabs.co/cache/batch",
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            payload=payload
        )

        end_time = time.perf_counter()
        duration = end_time - start_time

        if api_data:
            import json
            with open("test_payload.json", "w") as file:
                json.dump(payload, file, indent=2)

            with open("response.json", "w") as file:
                json.dump(api_data, file, indent=2)

        print(api_data)
        print("------------")
        print(f"The operation took {duration:.6f} seconds.")  #


    async def run_bettorodds_external_mapper(self, session: aiohttp.ClientSession, sportsbook_data: list):
        if not sportsbook_data:
            return []

        payload_data = self.build_bettorodds_external_mapper_data(sportsbook_data)
        for league, league_data in payload_data.items():
            if league == "NBA":
                test_payload = league_data[0]
                await self.bettor_odds_external_caller(session=session, payload=test_payload, league="NBA")

        # test_payload = payload_data.get("NBA")

        # await self.bettor_odds_external_caller(session=session, payload=test_payload)

    def build_bettorodds_external_mapper_data(self, sportsbook_data: list) -> dict:
        mapping_dict = {}

        for data in sportsbook_data:
            league = data.league

            mapping_dict.setdefault(
                league,
                {
                    "teams": set(),
                    "players": set(),
                    "markets": set(),
                }
            )

            mapping_dict[league]["teams"].add(data.team_data.team_a)
            mapping_dict[league]["teams"].add(data.team_data.team_b)

            for odds in data.odds:
                mapping_dict[league]["players"].add(odds.player_name)
                mapping_dict[league]["markets"].add(odds.stat_type)

        batched_data = {
            league: {
                k: list(batched(v, 15))
                for k, v in league_data.items()
            }
            for league, league_data in mapping_dict.items()
        }

        return {
            league: [
                {
                    "team": list(teams) or [],
                    "player": list(players) or [],
                    "market": list(markets) or [],
                }
                for teams, players, markets in zip_longest(
                    league_data.get("teams", []),
                    league_data.get("players", []),
                    league_data.get("markets", []),
                    fillvalue=[]
                )
            ]
            for league, league_data in batched_data.items()
        }


        # return [
        #     {
        #         "team": list(teams) or [],
        #         "player": list(players) or [],
        #         "market": list(markets) or [],
        #     }
        #     for teams, players, markets in zip_longest(
        #         batched_data["teams"],
        #         batched_data["players"],
        #         batched_data["markets"],
        #         fillvalue=[]  # Provide an empty list if you can't zip.
        #     )
        # ]




        # mapping_dict = {
        #     "teams": set(),
        #     "players": set(),
        #     "markets": set(),
        # }
        #
        # for data in sportsbook_data:
        #     league = data.league
        #
        #     mapping_dict.setdefault(league, set()).add(data.team_data.team_name)
        #
        #     mapping_dict["teams"].add(data.team_data.team_a)
        #     mapping_dict["teams"].add(data.team_data.team_b)
        #
        #     for odds in data.odds:
        #         mapping_dict["players"].add(odds.player_name)
        #         mapping_dict["markets"].add(odds.stat_type)


        # batched_data = {k: list(batched(v, 15)) for k, v in mapping_dict.items()}
        #
        # return [
        #     {
        #         "team": list(teams) or [],
        #         "player": list(players) or [],
        #         "market": list(markets) or [],
        #     }
        #     for teams, players, markets in zip_longest(
        #         batched_data["teams"],
        #         batched_data["players"],
        #         batched_data["markets"],
        #         fillvalue=[] # Provide an empty list if you can't zip.
        #     )
        # ]

    async def external_mapper(self, sportsbook_data: list):
        """Maps the sportsbook data using external mappings."""
        raw_unique_data_passer = [
            {
                "player_name": odds.player_name,
                "league": data.league,
                "combo": odds.combo,
                "solo_game": data.solo_game,
                "future": odds.future,
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







