import asyncio
import aiohttp
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class KiblMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="bet105", category="sportsbooks")

    async def get_leagues(self, session: CurlAsyncSession, auth_header: dict) -> dict:
        """Get the list of supported leagues"""

        raw_leagues = await self.api_caller(
            session=session,
            url=self.book_data.url.get("leagues"),
            headers=auth_header,
            method=self.book_data.method
        )

        excluded_leagues = ["WTA", 'MMA', "UFC", "BOX", "ATP"] # REMOVE AFTER INVERSE CALCULATIONS IS FIXED

        return {
            str(league.get("league_id")): {
                "league_name": league.get("name"),
                "league_abbr": league.get("abrv"),
            }

            for league in raw_leagues.get("result", [])
            if league and raw_leagues.get("result")
               and league.get("abrv") not in excluded_leagues and "tennis" not in league.get("name").lower() # REMOVE AFTER INVERSE CALCULATIONS IS FIXED
        }

    async def get_sportsbooks(self, session: CurlAsyncSession, auth_header: dict) -> list:
        """Get the list of supported sportsbooks"""
        raw_books = await self.api_caller(
                    session=session,
                    url=self.book_data.url.get("sportsbooks"),
                    headers=auth_header,
                    method=self.book_data.method
                )

        return [
            {
                "book_name": book.get("name"),
                "feed_source_id": book.get("feed_source_id"),
            }

            for book in raw_books.get("result", [])
            if raw_books.get("result")
        ]


    async def get_mapping_types(self, session: CurlAsyncSession, url_key: str, mapping_key_name: str,
                                mapping_value_name: str, auth_header: dict) -> dict:
        """
        Generic method to get mapping types from the API
        @param session: aiohttp ClientSession
        @param url_key: Key to access the URL from book_data
        @param mapping_key_name: The key name to map
        @param mapping_value_name: The value name to map
        """
        if not all([url_key, mapping_key_name, mapping_value_name]):
            raise ValueError("All parameters must be provided and non-empty.")

        raw_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get(url_key),
            headers=auth_header,
            method=self.book_data.method
        )

        return {
            str(data.get(mapping_key_name)): data.get(mapping_value_name)
            for data in raw_data.get("result", [])
            if data and raw_data.get("result")
        }

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager):
        redis_auth_instance = RedisAsyncManager(database=5)

        auth_token = await redis_auth_instance.get_data(self.book_data.auth_job_dict.auth_redis_key)

        if not auth_token:
            return

        auth_header = {"Authorization": auth_token}
        sportsbooks = await self.get_sportsbooks(session, auth_header)
        leagues = await self.get_leagues(session, auth_header)

        market_mapper_dict = {
            "segments": ["segment_id", "name"],  # Full Game, First Quarter, etc..
            "sides": ["side_id", "name"],  # Home, Away, Over, Under, Yes etc..
            "market_status": ["market_status_id", "name"],  # Open, Closed, Suspended, etc..
            "market_types": ["market_type_id", "name"],  # Spread, Moneyline, SOG, etc..
            "fixture_types": ["fixture_type_id", "name"],  # Future, Player Prop, Team
        }

        tasks = [
            self.get_mapping_types(
                session=session,
                url_key=url_key,
                mapping_key_name=mapping_info[0],
                mapping_value_name=mapping_info[1],
                auth_header=auth_header
            )

            for url_key, mapping_info in market_mapper_dict.items()
        ]

        results = await asyncio.gather(*tasks)

        mapped_results = {
            url_key: result
            for (url_key, _), result in zip(market_mapper_dict.items(), results)
        }

        mapped_data = {
            "sportsbooks": sportsbooks,
            "leagues": leagues,
            **mapped_results
        }

        any_empty = any(not item for item in mapped_data.values() if isinstance(item, list))

        if not mapped_data or any_empty:
            return

        await redis_instance.store_data(
            key_name=self.mapper_id_name,
            data_to_store=mapped_data,
            key_expiration=90000 # 25 Hour Expiration
        )

if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = KiblMapper()
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            await mapper.run_scheduler(session, redis_instance)
    asyncio.run(main())