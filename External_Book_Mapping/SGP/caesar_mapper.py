import asyncio
from itertools import chain
import random
from Authentication.caesars_auth import CaesarAuth
from Database.database import Database
from External_Book_Mapping.base_mapper import BaseMapper
from Redis.redis_manager import RedisAsyncManager
import os
from curl_cffi import AsyncSession as CurlAsyncSession

### CHECK MAPPING - MOENYLINE/RUNS AND OTHERS DON'T BE SHOWING ###


class CaesarMapper(BaseMapper):
    VALID_SPORTS = ["basketball", "baseball", "icehockey"]
    PROXY_URL = os.getenv("DECODO_PROXY")

    if not PROXY_URL:
        raise ValueError("CAESAR_PROXY environment variable is not set.")

    def __init__(self):
        super().__init__(book_name="caesars", category="sgp")

    async def _get_path_cache(self, redis_instance: RedisAsyncManager):
        cache = await redis_instance.get_data("caesar_path_cache")
        if not cache:
            return False, {}

        return True, cache

    async def _extract_cache(self, session, waf_token, redis_instance: RedisAsyncManager):
        raw_events = [
            self.api_caller(
                uset_proxy=True,
                url=self.book_data.mapping.url.get("event_url").format(sport=sport),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
            )
            for sport in CaesarMapper.VALID_SPORTS
        ]

        event_results = await asyncio.gather(*raw_events)

        event_ids = set(
            event.get("id")
            for result in event_results
            if result
            for competition in result.get("competitions", [])
            for event in competition.get("events", [])
        )

        if not event_ids:
            return set()

        game_url_semaphore = asyncio.Semaphore(3)  # same cap as fetch_market

        async def fetch_game_url(event):
            async with game_url_semaphore:
                result = await self.api_caller(
                    uset_proxy=True,
                    url=self.book_data.mapping.url.get("game_url").format(event_id=event),
                    method=self.book_data.mapping.method,
                    headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
                )
                await asyncio.sleep(random.uniform(0.05, 0.2))
                return result

        paths = set()
        game_url_results = await asyncio.gather(*(fetch_game_url(event) for event in event_ids))

        # game_url_tasks = [
        #     proxy_manager.proxy_caller(
        #         book_name=self.book_data.name,
        #         session=session,
        #         url=self.book_data.mapping.url.get("game_url").format(event_id=event),
        #         method=self.book_data.mapping.method,
        #         headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
        #         parse_json=True
        #     )
        #     for event in event_ids
        # ]
        #
        # paths = set()
        # game_url_results = await asyncio.gather(*game_url_tasks)

        for result in game_url_results:
            if result and result.get("event", {}).get("id"):
                paths.update(
                    tab.get("dataPath")
                    for tab in result.get("tabs", [])
                    if tab.get("dataPath") and not result.get("event", {}).get("started")
                )

        if paths:
            await redis_instance.store_data(
                key_name="caesar_path_cache",
                data_to_store=list(paths),
                key_expiration=3600
            )

        return paths

    def _create_mapping(self, event_data: dict):
        results = {}

        for market_group in chain.from_iterable(
            event_data.get("event", {}).get("keyMarketGroups", [])
            for event_data in [event_data]
        ):
            for market in market_group.get("markets", []):
                for selection in market.get("selections", []):
                    results[selection.get("id")] = {
                        "event_id": selection.get("eventId"),
                        "market_id": market.get("id"),
                        "selection_id": selection.get("id"),
                        "line": market.get("metadata", {}).get("line"),
                    }

        return results


    async def _get_waf_token(self):
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("caesars_waf_token")

    async def run_scheduler(self, session, redis_instance: RedisAsyncManager) -> bool:
        # caesar = CaesarAuth()
        waf_token = await self._get_waf_token()
        if not waf_token:
            return False

        had_cache, cache_data = await self._get_path_cache(redis_instance)

        if not had_cache:
            print("No cache found, extracting paths...")
            cache_data = await self._extract_cache(session, waf_token, redis_instance)

            if not cache_data:
                return False
                # return await self.run_scheduler(session, redis_instance)

            print(f"Extracted {len(cache_data)} paths and stored in cache.")
        else:
            print("Using cached paths for mapping.")

        semaphore = asyncio.Semaphore(3)

        async def fetch_market(path, waf_token):
            async with semaphore:
                return await self.api_caller(
                    uset_proxy=True,
                    url=self.book_data.mapping.url.get("market_url").format(path=path),
                    method=self.book_data.mapping.method,
                    headers={**self.book_data.mapping.headers,
                             "x-aws-waf-token": waf_token},
                )

        for _ in range(3):
            market_url_results = await asyncio.gather(*[fetch_market(path, waf_token) for path in cache_data])

            mapping = {}
            for result in market_url_results:
                if result:
                    mapping.update(self._create_mapping(result))

            if mapping:
                print(f"Found {len(mapping)} mappings.")
                await redis_instance.store_data(
                    key_name=self.mapper_id_name,
                    data_to_store=mapping,
                    key_expiration=800
                )
                return True

            print("No mapping found, retrying in 1-3 seconds...")
            await asyncio.sleep(random.uniform(1, 3))

        return False

if __name__ == "__main__":

    db = Database()
    redis_instance = RedisAsyncManager(database=2)
    mapper = CaesarMapper()

    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)

    asyncio.run(main())