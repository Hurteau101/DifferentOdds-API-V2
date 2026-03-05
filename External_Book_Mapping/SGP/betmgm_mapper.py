import asyncio
import math
import re
from math import ceil
from collections import defaultdict
from itertools import chain
import aiohttp

from Database.database import Database
from External_Book_Mapping.base_mapper import BaseMapper
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

    def _map_parent_data(self, parent_data: dict, parent_fixture_id: int, market_name: str, original_line: str | int, market_unique_id: int):
        if not all([parent_data, parent_fixture_id, market_name, original_line]):
            return {}

        found_mapping = parent_data.get(parent_fixture_id, {}).get(market_name)

        # Check if number ends in .5
        if bool(re.match(r"^\d+\.5$", original_line)):
            if isinstance(original_line, str):
                original_line = float(original_line)

            rounded_up_line = str(int(math.ceil(original_line)))
            found_match = next((
                mapping
                for mapping in found_mapping
                if market_unique_id != mapping.get("id") and rounded_up_line == mapping.get("line")
            ), None)

            if found_match:
                return found_match

        return {}

    def _filter_mapping(self, raw_data: dict) -> dict:


        # Create a parent mapping, to formulate lines where there is a milestone attached.
        # As sometimes the SGP won't work for a 1.5 line, but will work for a milestone of 2+
        parent_ids = {}

        for data in raw_data.get("fixtures", []):
            for option_list in data.get("optionMarkets", []):
                parent_id = option_list.get("fixtureParticipantId")

                if parent_id:
                    parent_bucket = parent_ids.setdefault(parent_id, {})

                    parameter_list = option_list.get("parameters", [])

                    market_name = next(
                        (parameter.get("value") for parameter in parameter_list if parameter.get("key") == "Happening"),
                        None)

                    if market_name:
                        happening_bucket = parent_bucket.setdefault(market_name, [])

                        happening_bucket.append({
                            "id": option_list.get("id"),
                            "name": option_list.get("name", {}).get("value"),
                            "line": option_list.get("attr"),
                            "game_id": option_list.get("id"),
                            "fixture_id": data.get("id"),
                            "group_id": data.get("addons", {}).get("betBuilderId"),
                            "fixture_id_v2": data.get("addons", {}).get("betBuilderTradingV2FixtureId"),
                            "source": option_list.get("source"),
                            "bet_id": next((
                                option.get("id")
                                for option in option_list.get("options", [])
                            ))
                        })

        return {
            str(option.get("id")): {
                "game_id": option_list.get("id"),
                "fixture_id": data.get("id"),
                "group_id": data.get("addons", {}).get("betBuilderId"),
                "fixture_id_v2": data.get("addons", {}).get("betBuilderTradingV2FixtureId"),
                "source": option_list.get("source"),
                "is_sgp_eligible": option_list.get("isBetBuilder"),
                "parent_data": self._map_parent_data(
                    parent_data=parent_ids,
                    parent_fixture_id=option_list.get("fixtureParticipantId"),
                    market_name=next((
                        parameter.get("value") for parameter in option_list.get("parameters", []) if parameter.get("key") == "Happening"
                    ), None),
                    original_line=option_list.get("attr"),
                    market_unique_id=option_list.get("id")
                )
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

if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BetMgmMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())