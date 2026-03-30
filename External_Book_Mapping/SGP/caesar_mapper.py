import asyncio
from itertools import chain
import random
import aiohttp
import os
from Database.database import Database
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.proxy_manger import ProxyManager
from Utils.request_caller import SportbookRequestType


class CaesarMapper(BaseMapper):
    # Find 'sportId' [FYI 'football' = soccer]
    VALID_SPORTS = ["basketball", "baseball", "boxing", "football", "icehockey", "americanfootball", "ufcmma", "tennis"]
    def __init__(self):
        super().__init__(book_name="caesars", category="sgp", request_type=SportbookRequestType.SPOOF)

    async def _get_waf_token(self):
        """Extract WAF token from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("caesars_waf_token")

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

    async def _random_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    async def _limited_gather(self, tasks, limit: int = 5):
        semaphore = asyncio.Semaphore(limit)

        async def sem_task(task):
            async with semaphore:
                result = await task
                # await self._random_delay()
                return result

        return await asyncio.gather(*[sem_task(t) for t in tasks])


    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        waf_token = await self._get_waf_token()

        if not waf_token:
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_auth",
                message="Couldn't find WAF token in redis",
                level="error"
            )

            return

        proxy = os.getenv("RESIDENTIAL_PROXIES")
        if not proxy:
            create_sentry_message(
                tag_key="caesars",
                tag_value="proxy_failure",
                message="No proxy found",
                level="error"
            )
            return

        proxies = proxy.split(",")
        proxy_manager = ProxyManager(proxies=proxies, api_caller_func=self.api_caller)

        raw_events = [
            proxy_manager.proxy_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("event_url").format(sport=sport),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
                parse_json=True
            )
            for sport in CaesarMapper.VALID_SPORTS
        ]

        event_results = await self._limited_gather(raw_events, limit=5)

        event_ids = set(
            event.get("id")
            for result in event_results
            if result
            for competition in result.get("competitions", [])
            for event in competition.get("events", [])
        )

        if not event_ids:
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_events",
                message="No event IDs found during Caesar mapping.",
                level="error"
            )

            return

        game_url_tasks = [
            proxy_manager.proxy_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("game_url").format(event_id=event),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
                parse_json=True
            )
            for event in event_ids
        ]

        paths = set()

        game_url_results = await self._limited_gather(game_url_tasks, limit=5)

        for result in game_url_results:
            if result and result.get("event", {}).get("id"):
                paths.update(
                    tab.get("dataPath")
                    for tab in result.get("tabs", [])
                    if tab.get("dataPath")
                )

        if not paths:
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_paths",
                message="No market paths found during Caesar mapping.",
                level="error"
            )
            return

        market_url_tasks = [
            proxy_manager.proxy_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("market_url").format(path=path),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token,
                         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
                         'Accept': 'application/json',
                         'Accept-Language': 'en-US,en;q=0.9',
                         'Accept-Encoding': 'gzip, deflate, br, zstd',
                         'Referer': 'https://sportsbook.caesars.com/',
                         'content-type': 'application/json',
                         'x-app-version': '7.42.1',
                         'x-platform': 'cordova-desktop',
                         'x-unique-device-id': '53c26028-d052-4871-83e7-a6cbf3686f57',
                         'Origin': 'https://sportsbook.caesars.com',
                         'Connection': 'keep-alive',
                         'Sec-Fetch-Dest': 'empty',
                         'Sec-Fetch-Mode': 'cors',
                         'Sec-Fetch-Site': 'cross-site',
                         'Priority': 'u=0',
                         'TE': 'trailers'
                         },
                parse_json=True
            )
            for path in paths
        ]

        market_url_results = await self._limited_gather(market_url_tasks, limit=3)


        if not market_url_results:
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_market_data",
                message="No market data found during Caesar mapping.",
                level="error"
            )
            return

        mapping = {}

        for result in market_url_results:
            if result:
                mapping.update(self._create_mapping(result))

        if mapping:
            await redis_instance.store_data(
                key_name="caesar_mapped_ids",
                data_to_store=mapping,
                key_expiration=600
            )

if __name__ == "__main__":
    from curl_cffi import AsyncSession as CurlAsyncSession
    db = Database()
    redis_instance = RedisAsyncManager(database=2)
    mapper = CaesarMapper()
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
        # async with aiohttp.ClientSession() as session:
        #     await mapper.run_scheduler(session=session, redis_instance=redis_instance)

    asyncio.run(main())