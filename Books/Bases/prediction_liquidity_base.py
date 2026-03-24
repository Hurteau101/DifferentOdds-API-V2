from datetime import datetime, timezone

import aiohttp
from Books.Bases.book_base import BookBase
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

class PredictionLiquidityBase(BookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="prediction_liquidity", book_name=book_name, request_type=request_type, redis_database=1,
                         payload_batch=10, async_batch=20, expiration_time=600)

    async def _store_chunk_data(self, data_to_store: dict | list, book_name: str, timestamp_data: bool):
        """Used to store chunks of data (aka each market is in its own dict)"""
        if not data_to_store:
            return

        redis_instance = RedisAsyncManager(database=self.redis_database)

        stored_data = data_to_store

        if timestamp_data:
            stored_data = {
                "last_refresh": datetime.now(timezone.utc).isoformat(),
                "data": data_to_store
            }

        await redis_instance.store_data(
            key_name=f"{book_name}_chunked",
            data_to_store=stored_data,
            key_expiration=self.expiration_time
        )

    async def market_chunk_processor(self, mapped_data: list, book_name: str, timestamp_data: bool = False):
        """Group the data by market and store in redis cache"""
        game_data = [
            {
                "event_name": market.event_name,
                "league": market.league,
                "start_date": market.start_date,
                "team_data": market.team_data,
                "selection_key": {
                    "market": odds.market,
                    "event_name": market.event_name,
                    "line": odds.line,
                    "bet_type": odds.bet_type,
                    "bet_team": odds.bet_team,
                    "bet_player": odds.bet_player,
                },
                "liquidity_data": odds.liquidity_data,
            }
            for market in mapped_data
            for odds in market.odds
        ]

        if game_data:
            await self._store_chunk_data(data_to_store=game_data, book_name=book_name, timestamp_data=timestamp_data)

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