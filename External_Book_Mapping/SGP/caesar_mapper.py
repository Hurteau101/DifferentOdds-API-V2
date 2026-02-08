import asyncio
from itertools import chain

import aiohttp
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class CaesarMapper(BaseMapper):
    VALID_SPORTS = ["basketball", "baseball", "boxing", "football", "icehockey", "soccer", "ufcmma"]
    def __init__(self):
        super().__init__(book_name="caesars", category="sgp", request_type=SportbookRequestType.ASYNC)

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

        raw_events = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("event_url").format(sport=sport),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token}
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

            return

        game_url_tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("game_url").format(event_id=event),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token}
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
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("market_url").format(path=path),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers, "x-aws-waf-token": waf_token}
            )
            for path in paths
        ]

        market_url_results = await asyncio.gather(*market_url_tasks)

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