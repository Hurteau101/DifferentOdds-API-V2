import aiohttp
from dotenv import load_dotenv
from Books.Bases.book_base import BookBase
from Utils.request_caller import SportbookRequestType
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData

class DFSBookBase(BookBase):
    load_dotenv()
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="DFS", book_name=book_name, request_type=request_type, redis_database=0, payload_batch=10, async_batch=20)
        self.esport_leagues = ["LOL", "CS2", "DOTA2", "VAL", "COD", "APEX", "R6"]

    # def player_team_mapper(self, stats: DFSStats, mapped_teams: dict):
    #     """Maps the player's team name in the game data if it matches the original team name."""
    #     player_team = stats.player_team
    #
    #     if player_team and player_team.lower() == mapped_teams["original_name"].lower():
    #         stats.player_team = mapped_teams["team_name"]

    def yield_game_data(self, book_data):
        """Helper function to yield game data from nested lists. Must follow specific structure of list of lists.
        With no inner function call to extract data"""
        for game in book_data:
            for game_data in game:
                if game_data:
                    yield game_data

    def market_mapper(self, stats: DFSStats, mapped_markets: dict, league: str):
        """Maps the market name in the game data if it matches the original market name."""
        stat_type = stats.stat_type.lower()
        stat_key = f"{stat_type}-{league.lower()}"

        if mapped_markets.get(stat_key):
            stats.stat_type = mapped_markets[stat_key]

    def solo_mapper(self, stats: DFSStats, game_data: GameData, mapped_players: dict):
        """Maps the player's name in the game data if it matches a solo game."""

        def find_player(player_name: str):
            player_key = f"{player_name.lower()}-{game_data.league.lower()}"
            return mapped_players.get(player_key)

        def map_team(team: str):
            if not team:
                return team

            team = team.lower()

            found_dict = next((
                player
                for player in mapped_players.values()
                if player.get("original_name").lower() == team or team.lower() in player.get("original_name").lower()
            ), None)

            return found_dict.get("player_name") if found_dict else team

        for stat in stats:
            found_player = find_player(player_name=stat.player_name)

            if found_player:
                player_name = found_player.get("player_name")
                stat.player_name = player_name
                game_data.league = found_player["league"]
                game_data.player_team = player_name

        team_a = game_data.team_data.team_a
        team_b = game_data.team_data.team_b

        if team_a and team_b:
            for side in ["team_a", "team_b"]:
                team_name_attr = getattr(game_data.team_data, side, None)
                team_name = map_team(team_name_attr)
                if not team_name:
                    continue

                setattr(game_data.team_data, side, team_name)

            game_data.event_name = " vs ".join(sorted([game_data.team_data.team_a, game_data.team_data.team_b]))
            game_data.game_key = self.generate_key(
                [game_data.team_data.team_a, game_data.team_data.team_b, game_data.start_date])


    async def map_runner(self, sportsbook_data: list, session: aiohttp.ClientSession = None):
        mapped_data = await self.bettorodds_mapping.run_mapping(session=session, sportsbook_data=sportsbook_data)

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

        mappings = await self.combine_bettorodds_internal_mapping(
            raw_unique_data=raw_unique_data_passer,
            bettorodds_mapped_data=mapped_data
        )

        teams = mappings.get("teams", {})
        players = mappings.get("players", {})
        markets = mappings.get("markets", {})

        return self.map_data(
            original_sportsbook_data=sportsbook_data,
            mapped_teams=teams,
            mapped_players=players,
            mapped_markets=markets,
            solo_game_mapper_func=self.solo_mapper,
        )







