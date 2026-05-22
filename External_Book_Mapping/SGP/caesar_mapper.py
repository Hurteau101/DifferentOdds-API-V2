# import asyncio
# from itertools import chain
# import aiohttp
# import os
# from Database.database import Database
# from External_Book_Mapping.base_mapper import BaseMapper
# from Monitoring.monitoring import create_sentry_message
# from Redis.redis_manager import RedisAsyncManager
# from Utils.proxy_manger import ProxyManager
# from Utils.request_caller import SportbookRequestType
# #
# #
# # class CaesarMapper(BaseMapper):
# #     # Find 'sportId' [FYI 'football' = soccer]
# #     # VALID_SPORTS = ["basketball", "baseball", "boxing", "football", "icehockey", "americanfootball", "ufcmma", "tennis"]
# #     VALID_SPORTS = ["basketball", "baseball", "icehockey"]
# #     def __init__(self):
# #         super().__init__(book_name="caesars", category="sgp", request_type=SportbookRequestType.SPOOF)
# #
# #     async def _get_waf_token(self):
# #         """Extract WAF token from Redis."""
# #         redis_instance = RedisAsyncManager(database=5)
# #         return await redis_instance.get_data("caesars_waf_token")
# #
# #     async def _get_path_cache(self, redis_instance: RedisAsyncManager):
# #         """Check Redis for cached paths to avoid redundant API calls."""
# #         cache = await redis_instance.get_data("caesar_path_cache")
# #         if not cache:
# #             return False, {}
# #
# #         return True, cache
# #
# #     async def _extract_cache(self, proxy_manager: ProxyManager, session: aiohttp.ClientSession, waf_token: str,
# #                              redis_instance: RedisAsyncManager):
# #         raw_events = [
# #             proxy_manager.proxy_caller(
# #                 book_name=self.book_data.name,
# #                 session=session,
# #                 url=self.book_data.mapping.url.get("event_url").format(sport=sport),
# #                 method=self.book_data.mapping.method,
# #                 headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
# #                 parse_json=True
# #             )
# #             for sport in CaesarMapper.VALID_SPORTS
# #         ]
# #
# #         event_results = await asyncio.gather(*raw_events)
# #
# #         event_ids = set(
# #             event.get("id")
# #             for result in event_results
# #             if result
# #             for competition in result.get("competitions", [])
# #             for event in competition.get("events", [])
# #         )
# #
# #         if not event_ids:
# #             create_sentry_message(
# #                 tag_key="caesars",
# #                 tag_value="no_events",
# #                 message="No event IDs found during Caesar mapping.",
# #                 level="error"
# #             )
# #
# #             return
# #
# #         game_url_tasks = [
# #             proxy_manager.proxy_caller(
# #                 book_name=self.book_data.name,
# #                 session=session,
# #                 url=self.book_data.mapping.url.get("game_url").format(event_id=event),
# #                 method=self.book_data.mapping.method,
# #                 headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
# #                 parse_json=True
# #             )
# #             for event in event_ids
# #         ]
# #
# #         paths = set()
# #
# #         game_url_results = await asyncio.gather(*game_url_tasks)
# #
# #         for result in game_url_results:
# #             if result and result.get("event", {}).get("id"):
# #                 paths.update(
# #                     tab.get("dataPath")
# #                     for tab in result.get("tabs", [])
# #                     if tab.get("dataPath") and not result.get("event", {}).get("started")
# #                 )
# #
# #         if paths:
# #             await redis_instance.store_data(
# #                 key_name="caesar_path_cache",
# #                 data_to_store=list(paths),
# #                 key_expiration=3600  # 1 Hour
# #             )
# #
# #         return paths
# #
# #     def _create_mapping(self, event_data: dict):
# #         results = {}
# #
# #         for market_group in chain.from_iterable(
# #             event_data.get("event", {}).get("keyMarketGroups", [])
# #             for event_data in [event_data]
# #         ):
# #             for market in market_group.get("markets", []):
# #                 for selection in market.get("selections", []):
# #                     results[selection.get("id")] = {
# #                         "event_id": selection.get("eventId"),
# #                         "market_id": market.get("id"),
# #                         "selection_id": selection.get("id"),
# #                         "line": market.get("metadata", {}).get("line"),
# #                     }
# #
# #         return results
# #
# #     async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
# #         waf_token = await self._get_waf_token()
# #
# #         if not waf_token:
# #             create_sentry_message(
# #                 tag_key="caesars",
# #                 tag_value="no_auth",
# #                 message="Couldn't find WAF token in redis",
# #                 level="error"
# #             )
# #
# #             return False
# #
# #         proxy = os.getenv("RESIDENTIAL_PROXIES")
# #         if not proxy:
# #             create_sentry_message(
# #                 tag_key="caesars",
# #                 tag_value="proxy_failure",
# #                 message="No proxy found",
# #                 level="error"
# #             )
# #             return False
# #
# #         proxies = proxy.split(",")
# #         proxy_manager = ProxyManager(proxies=proxies, api_caller_func=self.api_caller)
# #
# #         had_cache, cache_data = await self._get_path_cache(redis_instance)
# #
# #         if not had_cache:
# #             print("No cache found, extracting paths...")
# #             cache_data = await self._extract_cache(proxy_manager, session, waf_token, redis_instance)
# #             print(f"Extracted {len(cache_data)} paths and stored in cache.")
# #         else:
# #             print("Using cached paths for mapping.")
# #
# #         market_url_tasks = [
# #             proxy_manager.proxy_caller(
# #                 book_name=self.book_data.name,
# #                 session=session,
# #                 url=self.book_data.mapping.url.get("market_url").format(path=path),
# #                 method=self.book_data.mapping.method,
# #                 headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token,
# #                          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
# #                          'Accept': 'application/json',
# #                          'Accept-Language': 'en-US,en;q=0.9',
# #                          'Accept-Encoding': 'gzip, deflate, br, zstd',
# #                          'Referer': 'https://sportsbook.caesars.com/',
# #                          'content-type': 'application/json',
# #                          'x-app-version': '7.42.1',
# #                          'x-platform': 'cordova-desktop',
# #                          'x-unique-device-id': '53c26028-d052-4871-83e7-a6cbf3686f57',
# #                          'Origin': 'https://sportsbook.caesars.com',
# #                          'Connection': 'keep-alive',
# #                          'Sec-Fetch-Dest': 'empty',
# #                          'Sec-Fetch-Mode': 'cors',
# #                          'Sec-Fetch-Site': 'cross-site',
# #                          'Priority': 'u=0',
# #                          'TE': 'trailers'
# #                          },
# #                 parse_json=True
# #             )
# #             for path in cache_data
# #         ]
# #
# #         market_url_results = await asyncio.gather(*market_url_tasks)
# #
# #         if not market_url_results:
# #             create_sentry_message(
# #                 tag_key="caesars",
# #                 tag_value="no_market_data",
# #                 message="No market data found during Caesar mapping.",
# #                 level="error"
# #             )
# #             return False
# #
# #         mapping = {}
# #
# #         for result in market_url_results:
# #             if result:
# #                 mapping.update(self._create_mapping(result))
# #
# #
# #         if mapping:
# #             await redis_instance.store_data(
# #                 key_name="caesar_mapped_ids",
# #                 data_to_store=mapping,
# #                 key_expiration=600
# #             )
# #
# #             return True
# #
# #         return False
# #
# # if __name__ == "__main__":
# #     from curl_cffi import AsyncSession as CurlAsyncSession
# #     db = Database()
# #     redis_instance = RedisAsyncManager(database=2)
# #     mapper = CaesarMapper()
# #     async def main():
# #         async with CurlAsyncSession(impersonate="safari15_5") as session:
# #             await mapper.run_scheduler(session=session, redis_instance=redis_instance)
# #         # async with aiohttp.ClientSession() as session:
# #         #     await mapper.run_scheduler(session=session, redis_instance=redis_instance)
# #
# #     asyncio.run(main())
#
#
#
# import asyncio
# import random
# from itertools import chain
# import aiohttp
# import os
# from Database.database import Database
# from External_Book_Mapping.base_mapper import BaseMapper
# from Monitoring.monitoring import create_sentry_message
# from Redis.redis_manager import RedisAsyncManager
# from Utils.proxy_manger import ProxyManager
# from Utils.request_caller import SportbookRequestType
#
#
# class CaesarMapper(BaseMapper):
#     # Find 'sportId' [FYI 'football' = soccer]
#     # VALID_SPORTS = ["basketball", "baseball", "boxing", "football", "icehockey", "americanfootball", "ufcmma", "tennis"]
#     VALID_SPORTS = ["basketball", "baseball", "icehockey"]
#
#     def __init__(self):
#         super().__init__(book_name="caesars", category="sgp", request_type=SportbookRequestType.SPOOF)
#
#     async def _get_waf_token(self):
#         """Extract WAF token from Redis."""
#         redis_instance = RedisAsyncManager(database=5)
#         return await redis_instance.get_data("caesars_waf_token")
#
#     async def _get_path_cache(self, redis_instance: RedisAsyncManager):
#         """Check Redis for cached paths to avoid redundant API calls."""
#         cache = await redis_instance.get_data("caesar_path_cache")
#         if not cache:
#             return False, {}
#         return True, cache
#
#     async def _extract_cache(self, proxy_manager: ProxyManager, session: aiohttp.ClientSession, waf_token: str,
#                              redis_instance: RedisAsyncManager):
#         raw_events = [
#             proxy_manager.proxy_caller(
#                 book_name=self.book_data.name,
#                 session=session,
#                 url=self.book_data.mapping.url.get("event_url").format(sport=sport),
#                 method=self.book_data.mapping.method,
#                 headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
#                 parse_json=True
#             )
#             for sport in CaesarMapper.VALID_SPORTS
#         ]
#
#         event_results = await asyncio.gather(*raw_events)
#
#         event_ids = set(
#             event.get("id")
#             for result in event_results
#             if result
#             for competition in result.get("competitions", [])
#             for event in competition.get("events", [])
#         )
#
#         if not event_ids:
#             create_sentry_message(
#                 tag_key="caesars",
#                 tag_value="no_events",
#                 message="No event IDs found during Caesar mapping.",
#                 level="error"
#             )
#             return
#
#         game_url_tasks = [
#             proxy_manager.proxy_caller(
#                 book_name=self.book_data.name,
#                 session=session,
#                 url=self.book_data.mapping.url.get("game_url").format(event_id=event),
#                 method=self.book_data.mapping.method,
#                 headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token},
#                 parse_json=True
#             )
#             for event in event_ids
#         ]
#
#         paths = set()
#         game_url_results = await asyncio.gather(*game_url_tasks)
#
#         for result in game_url_results:
#             if result and result.get("event", {}).get("id"):
#                 paths.update(
#                     tab.get("dataPath")
#                     for tab in result.get("tabs", [])
#                     if tab.get("dataPath") and not result.get("event", {}).get("started")
#                 )
#
#         if paths:
#             await redis_instance.store_data(
#                 key_name="caesar_path_cache",
#                 data_to_store=list(paths),
#                 key_expiration=3600
#             )
#
#         return paths
#
#     def _create_mapping(self, event_data: dict):
#         results = {}
#
#         for market_group in chain.from_iterable(
#             event_data.get("event", {}).get("keyMarketGroups", [])
#             for event_data in [event_data]
#         ):
#             for market in market_group.get("markets", []):
#                 for selection in market.get("selections", []):
#                     results[selection.get("id")] = {
#                         "event_id": selection.get("eventId"),
#                         "market_id": market.get("id"),
#                         "selection_id": selection.get("id"),
#                         "line": market.get("metadata", {}).get("line"),
#                     }
#
#         return results
#
#     async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
#         waf_token = await self._get_waf_token()
#
#         if not waf_token:
#             create_sentry_message(
#                 tag_key="caesars",
#                 tag_value="no_auth",
#                 message="Couldn't find WAF token in redis",
#                 level="error"
#             )
#             return False
#
#         proxy = os.getenv("CAESAR_PROXIES")
#
#         # if not proxy:
#         #     create_sentry_message(
#         #         tag_key="caesars",
#         #         tag_value="proxy_failure",
#         #         message="No proxy found",
#         #         level="error"
#         #     )
#         #     return False
#         #
#         proxies = proxy.split(",")
#         proxy_manager = ProxyManager(proxies=proxies, api_caller_func=self.api_caller)
#
#         had_cache, cache_data = await self._get_path_cache(redis_instance)
#
#         if not had_cache:
#             print("No cache found, extracting paths...")
#             cache_data = await self._extract_cache(proxy_manager, session, waf_token, redis_instance)
#             print(f"Extracted {len(cache_data)} paths and stored in cache.")
#         else:
#             print("Using cached paths for mapping.")
#
#         print(f"Total paths to fetch: {len(cache_data)}")
#
#         semaphore = asyncio.Semaphore(5)
#
#         async def fetch_market(path):
#             async with semaphore:
#                 await asyncio.sleep(random.uniform(0.3, 0.8))
#                 return await proxy_manager.proxy_caller(
#                     book_name=self.book_data.name,
#                     session=session,
#                     url=self.book_data.mapping.url.get("market_url").format(path=path),
#                     method=self.book_data.mapping.method,
#                     headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token,
#                              'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
#                              'Accept': 'application/json',
#                              'Accept-Language': 'en-US,en;q=0.9',
#                              'Accept-Encoding': 'gzip, deflate, br, zstd',
#                              'Referer': 'https://sportsbook.caesars.com/',
#                              'content-type': 'application/json',
#                              'x-app-version': '7.42.1',
#                              'x-platform': 'cordova-desktop',
#                              'x-unique-device-id': '53c26028-d052-4871-83e7-a6cbf3686f57',
#                              'Origin': 'https://sportsbook.caesars.com',
#                              'Connection': 'keep-alive',
#                              'Sec-Fetch-Dest': 'empty',
#                              'Sec-Fetch-Mode': 'cors',
#                              'Sec-Fetch-Site': 'cross-site',
#                              'Priority': 'u=0',
#                              'TE': 'trailers'
#                              },
#                     parse_json=True
#                 )
#
#         market_url_results = await asyncio.gather(*[fetch_market(path) for path in cache_data])
#
#         if not market_url_results:
#             create_sentry_message(
#                 tag_key="caesars",
#                 tag_value="no_market_data",
#                 message="No market data found during Caesar mapping.",
#                 level="error"
#             )
#             return False
#
#         mapping = {}
#         for result in market_url_results:
#             if result:
#                 mapping.update(self._create_mapping(result))
#
#         if mapping:
#             print(mapping)
#             await redis_instance.store_data(
#                 key_name="caesar_mapped_ids",
#                 data_to_store=mapping,
#                 key_expiration=600
#             )
#             return True
#
#         return False
#
#
# if __name__ == "__main__":
#     from curl_cffi import AsyncSession as CurlAsyncSession
#     db = Database()
#     redis_instance = RedisAsyncManager(database=2)
#     mapper = CaesarMapper()
#
#     async def main():
#         async with CurlAsyncSession(impersonate="safari15_5") as session:
#             await mapper.run_scheduler(session=session, redis_instance=redis_instance)
#
#     asyncio.run(main())


import asyncio
import random
from itertools import chain
import os

import aiohttp

from Authentication.caesars_auth import CaesarAuth
from Database.database import Database
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.proxy_manger import ProxyManager
from Utils.request_caller import SportbookRequestType


class CaesarMapper(BaseMapper):
    VALID_SPORTS = ["basketball", "baseball", "icehockey"]

    def __init__(self):
        super().__init__(book_name="caesars", category="sgp", request_type=SportbookRequestType.SPOOF)

    async def _get_waf_token(self):
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("caesars_waf_token")

    async def _get_path_cache(self, redis_instance: RedisAsyncManager):
        cache = await redis_instance.get_data("caesar_path_cache")
        if not cache:
            return False, {}
        return True, cache

    async def _extract_cache(self, proxy_manager: ProxyManager, session, waf_token: str,
                             redis_instance: RedisAsyncManager):
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

        event_results = await asyncio.gather(*raw_events)

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
            return set()

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
        game_url_results = await asyncio.gather(*game_url_tasks)

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

    async def _recall_auth(self, proxy_index):
        redis_instance = RedisAsyncManager(database=5)
        caesar = CaesarAuth()
        async with aiohttp.ClientSession() as session:
            return await caesar.run_scheduler(session, redis_instance, proxy_index=proxy_index)

    async def run_scheduler(self, session, redis_instance: RedisAsyncManager) -> bool:
        waf_token_data = await self._get_waf_token()

        if not waf_token_data:
            return False

        waf_token = waf_token_data.get("waf_token")
        cookie_str = waf_token_data.get("cookie_str")
        proxy_index = waf_token_data.get("proxy_index")
        proxy_str = waf_token_data.get("proxy_str")


        if not all([waf_token is not None, cookie_str is not None, proxy_index is not None, proxy_str is not None]):
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_auth",
                message="Couldn't find WAF token in redis",
                level="error"
            )
            return False


        proxy_manager = ProxyManager(proxies=[proxy_str], api_caller_func=self.api_caller)

        had_cache, cache_data = await self._get_path_cache(redis_instance)

        if not had_cache:
            print("No cache found, extracting paths...")
            cache_data = await self._extract_cache(proxy_manager, session, waf_token, redis_instance)

            if not cache_data:
                create_sentry_message(
                    tag_key="caesars",
                    tag_value="no_paths",
                    message="No paths extracted",
                    level="error"
                )

                print("Retrying auth...")
                success = await self._recall_auth(proxy_index=proxy_index)

                if not success:
                    return False

                return await self.run_scheduler(session, redis_instance)


            print(f"Extracted {len(cache_data)} paths and stored in cache.")
        else:
            print("Using cached paths for mapping.")

        semaphore = asyncio.Semaphore(10)

        async def fetch_market(path):
            async with semaphore:
                return await proxy_manager.proxy_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("market_url").format(path=path),
                    method=self.book_data.mapping.method,
                    headers={**self.book_data.mapping.headers,
                             "x-aws-waf-token": waf_token,
                             "Cookie": cookie_str},
                    parse_json=True
                )

        market_url_results = await asyncio.gather(*[fetch_market(path) for path in cache_data])

        mapping = {}
        for result in market_url_results:
            if result:
                mapping.update(self._create_mapping(result))

        if mapping:
            await redis_instance.store_data(
                key_name="caesar_mapped_ids",
                data_to_store=mapping,
                key_expiration=800
            )
            return True

        success = await self._recall_auth(proxy_index=proxy_index)

        if not success:
            return False

        return await self.run_scheduler(session, redis_instance)

        #
        # semaphore = asyncio.Semaphore(1)
        #
        # async def fetch_market(path):
        #     async with semaphore:
        #         # await asyncio.sleep(random.uniform(0.3, 0.8))
        #         return await proxy_manager.proxy_caller(
        #             book_name=self.book_data.name,
        #             session=session,
        #             url=self.book_data.mapping.url.get("market_url").format(path=path),
        #             method=self.book_data.mapping.method,
        #             headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token,
        #                      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
        #                      'Accept': 'application/json',
        #                      'Accept-Language': 'en-US,en;q=0.9',
        #                      'Accept-Encoding': 'gzip, deflate, br, zstd',
        #                      'Referer': 'https://sportsbook.caesars.com/',
        #                      'content-type': 'application/json',
        #                      'x-app-version': '7.47.1',
        #                      'x-platform': 'cordova-desktop',
        #                      'x-unique-device-id': '53c26028-d052-4871-83e7-a6cbf3686f57',
        #                      'Origin': 'https://sportsbook.caesars.com',
        #                      'Connection': 'keep-alive',
        #                      'Sec-Fetch-Dest': 'empty',
        #                      'Sec-Fetch-Mode': 'cors',
        #                      'Sec-Fetch-Site': 'cross-site',
        #                      'Priority': 'u=0',
        #                      'TE': 'trailers'
        #                      },
        #             parse_json=True
        #         )
        #
        # market_url_results = await asyncio.gather(*[fetch_market(path) for path in cache_data])
        #
        # if not market_url_results:
        #     create_sentry_message(
        #         tag_key="caesars",
        #         tag_value="no_market_data",
        #         message="No market data found during Caesar mapping.",
        #         level="error"
        #     )
        #     return False
        #
        # mapping = {}
        # for result in market_url_results:
        #     if result:
        #         mapping.update(self._create_mapping(result))
        #
        # if mapping:
        #     await redis_instance.store_data(
        #         key_name="caesar_mapped_ids",
        #         data_to_store=mapping,
        #         key_expiration=600
        #     )
        #
        #     return True
        #
        # return False


if __name__ == "__main__":
    from curl_cffi import AsyncSession as CurlAsyncSession

    db = Database()
    redis_instance = RedisAsyncManager(database=2)
    mapper = CaesarMapper()

    async def main():
        async with CurlAsyncSession(impersonate="chrome120") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)

    asyncio.run(main())