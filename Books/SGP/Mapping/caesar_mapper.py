import asyncio
from itertools import chain
import random
from Books.Bases.mapper_base import MapperBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from loguru import logger


class CaesarMapper(MapperBase):
    VALID_SPORTS = ["basketball", "baseball", "icehockey"]

    def __init__(self):
        super().__init__(book_name="caesars", category="sgp")

    async def _get_path_cache(self):
        cache = await self.redis_manager.get_data("caesar_path_cache")
        if not cache:
            return False, {}

        return True, cache

    async def _extract_cache(self, waf_token: str):
        raw_events = [
            self.api_caller(
                use_proxy=True,
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
                    use_proxy=True,
                    url=self.book_data.mapping.url.get("game_url").format(event_id=event),
                    method=self.book_data.mapping.method,
                    headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
                )
                await asyncio.sleep(random.uniform(0.05, 0.2))
                return result

        paths = set()
        game_url_results = await asyncio.gather(*(fetch_game_url(event) for event in event_ids))

        for result in game_url_results:
            if result and result.get("event", {}).get("id"):
                paths.update(
                    tab.get("dataPath")
                    for tab in result.get("tabs", [])
                    if tab.get("dataPath") and not result.get("event", {}).get("started")
                )

        if paths:
            await self.store_data(
                key_name="caesar_path_cache",
                data_to_store=list(paths),
                expiration_time=3600
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

    async def run_mapper(self) -> bool:
        waf_token = await self.redis_auth_manager.get_data("caesar_auth")
        if not waf_token:
            logger.error("No WAF token found.")
            return False

        had_cache, cache_data = await self._get_path_cache()

        if not had_cache:
            logger.info("No cache found, extracting paths...")
            cache_data = await self._extract_cache(waf_token)

            if not cache_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="Couldn't extract paths from API."
                )
                return False

            logger.info(f"Extracted {len(cache_data)} paths and stored in cache.")
        else:
            logger.info("Using cached paths for mapping.")

        semaphore = asyncio.Semaphore(3)

        async def fetch_market(path, waf_token):
            async with semaphore:
                return await self.api_caller(
                    use_proxy=True,
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
                logger.info(f"Found {len(mapping)} mappings.")
                await self.store_data(
                    key_name=self.mapper_id_name,
                    data_to_store=mapping,
                    expiration_time=self.pre_calculated_redis_expiration
                )

                return True

            logger.info("No mappings found, retrying...")
            await asyncio.sleep(random.uniform(1, 3))


        insert_log(
            book_name=self.book_data.title,
            error_type=ErrorTypes.MAPPING,
            error_message="No mapping found"
        )

        return False

if __name__ == "__main__":
    caesar_mapper = CaesarMapper()
    asyncio.run(caesar_mapper.run_mapper())