import aiohttp
from Books.Bases.book_base import BookBase
from Utils.request_caller import SportbookRequestType
from Settings.Models.sportsbooks_models import SportsbookStats

class SportsbooksBookBase(BookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="sportsbooks", book_name=book_name, request_type=request_type, redis_database=6,
                         payload_batch=10, async_batch=20)

    async def map_runner(self, sportsbook_data: list, session: aiohttp.ClientSession = None):
        mapped_data = await self.bettorodds_mapping.run_mapping(session=session, sportsbook_data=sportsbook_data)

        raw_unique_data_passer = [
            {
                "player_name": odds.bet_player,
                "league": data.league,
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
        )