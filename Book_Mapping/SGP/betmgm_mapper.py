import asyncio
from itertools import chain
import aiohttp
from Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class BetMgmMapper(BaseMapper):
    VALID_LEAGUE_IDS = [
        23,  # Baseball
        11,  # Football
        12,  # Hockey
        7, # Basketball
    ]
    def __init__(self):
        super().__init__(book_name="betmgm", category="sgp", request_type=SportbookRequestType.ASYNC)

    def _filter_mapping(self, raw_data: dict) -> dict:
        # Map the ID's
        return {
            str(option.get("id")): {
                "game_id": option_list.get("id"),
                "group_id": data.get("addons", {}).get("betBuilderId"),
            }

            for data in raw_data.get("fixtures", [])
            for option_list in data.get("optionMarkets", [])
            for option in option_list.get("options", [])
        }

    async def _extract_mapping(self, session: aiohttp.ClientSession) -> dict | None:
        # Get all the mapping ID's for the leagues we want.
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("market_id_url").format(league_id=league_id),
                method=self.book_data.mapping.method,
                headers=self.book_data.mapping.headers
            )
            for league_id in BetMgmMapper.VALID_LEAGUE_IDS
        ]

        results = await asyncio.gather(*tasks)

        if not results:
            return None

        return dict(
            chain.from_iterable(self._filter_mapping(result).items() for result in results if result)
        )

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        mapped_ids = await self._extract_mapping(session=session)
        if not mapped_ids:
            create_sentry_message(
                tag_key="betmgm",
                tag_value="mapping_failure",
                message="No mapped IDs were extracted from BetMGM mapping.",
                level="error"
            )

        await redis_instance.store_data(
            key_name="betmgm_ids",
            data_to_store=mapped_ids,
            key_expiration=self.default_key_expiration
        )
