import asyncio
from itertools import chain
import aiohttp
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_mapper_base import SGPMapperBase

# Key selection ID

class Caesar_Mapper(SGPMapperBase):
    VALID_SPORTS = ["basketball", "baseball", "boxing", "football", "icehockey", "soccer", "ufcmma"]
    def __init__(self, waf_token):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="caesars", log_directory="SGP Mapper Logs",
                         log_name="caesar_mapper.log")
        self.waf_token = waf_token

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

    async def run_book(self):
        if not self.waf_token:
            return None

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("event_url").format(sport=sport),
                    method=self.book_data.method,
                    headers={**self.book_data.headers, "x-aws-waf-token": self.waf_token}
                )
                for sport in Caesar_Mapper.VALID_SPORTS
            ]

            raw_results = await asyncio.gather(*tasks)
            event_ids = set(
                event.get("id")
                for result in raw_results
                if result
                for competition in result.get("competitions", [])
                for event in competition.get("events", [])
            )

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("game_url").format(event_id=event),
                    method=self.book_data.method,
                    headers={**self.book_data.headers, "x-aws-waf-token": self.waf_token}
                )
                for event in event_ids
            ]

            paths = set()

            raw_results = await asyncio.gather(*tasks)
            for result in raw_results:
                if result and result.get("event", {}).get("id"):
                    paths.update(
                        tab.get("dataPath")
                        for tab in result.get("tabs", [])
                        if tab.get("dataPath")
                    )

            if not paths:
                return


            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_url").format(path=path),
                    method=self.book_data.method,
                    headers={**self.book_data.headers, "x-aws-waf-token": self.waf_token}
                )
                for path in paths
            ]

            raw_results = await asyncio.gather(*tasks)

            mapping = {}

            for result in raw_results:
                if result:
                    mapping.update(self._create_mapping(result))

            if mapping:
                redis = RedisManager(db=self.redis_db)
                await redis.store_data(
                    key_name="caesar_mapped_ids",
                    data_to_store=mapping,
                    key_expiration=self.key_expiration
                )


if __name__ == "__main__":
    async def main():
        redis_manager = RedisManager(db=5)
        return await redis_manager.get_auth_token("caesars_sgp_waf_token")


    waf_token = asyncio.run(main())
    mapper = Caesar_Mapper(waf_token=waf_token)
    asyncio.run(mapper.run_book())

    async def main():
        redis_client = RedisManager(db=2)
        mapped_data = await redis_client.fetch_data(key_name="caesar_mapped_ids")
        print(mapped_data)


    asyncio.run(main())

    # with open("caesar_mapped_ids.json", "w") as f:
    #     import json
    #     json.dump(test, f, indent=2)

    # with open("caesar_mapped_ids.json", "w") as f:
    #     import json
    #     json.dump(test, f, indent=2)