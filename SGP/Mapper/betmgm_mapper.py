import asyncio
from itertools import chain
import aiohttp
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_mapper_base import SGPMapperBase


class BetMGM_Mapper(SGPMapperBase):
    VALID_LEAGUE_IDS = [
        23,  # Baseball
        11,  # Football
        12,  # Hockey
    ]

    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="betmgm", log_directory="SGP Mapper Logs",
                         log_name="betmgm_mapper.log")

    def _filter_mapping(self, raw_data):
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

    async def _extract_mapping(self):
        # Get all the mapping ID's for the leagues we want.
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_id_url").format(league_id=league_id),
                    method=self.book_data.method,
                    headers=self.book_data.headers
                )
                for league_id in BetMGM_Mapper.VALID_LEAGUE_IDS
            ]

            raw_results = await asyncio.gather(*tasks)
            results = self.check_api_response(sportsbook="betmgm", results=raw_results)
            if not results:
                return

            return dict(
                chain.from_iterable(self._filter_mapping(result).items() for result in results if result)
            )

    async def run_book(self):
        mapped_ids = await self._extract_mapping()
        if mapped_ids:
            redis = RedisManager(db=self.redis_db)
            await redis.store_data(
                key_name="betmgm_ids",
                data_to_store=mapped_ids,
                key_expiration=self.key_expiration
            )

            await redis.close()


if __name__ == "__main__":
    betmgm_instance = BetMGM_Mapper()
    asyncio.run(betmgm_instance.run_book())