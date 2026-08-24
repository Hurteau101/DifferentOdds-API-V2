import asyncio
from External_Book_Mapping.base_mapper import BaseMapper
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class FanduelMapper(BaseMapper):
    # To find external IDs on fanduel, go to "All Sports" and click on the sport and you will see the network call
    # ex. https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7524&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FPhoenix

    EXTERNAL_MAPS = {
        "hockey": 7524,
        "baseball": 7511,
        "basketball": 7522,
        "football": 6423,
        "soccer": 1,
        "tennis": 2,
        "ufc": 26420387
    }

    def __init__(self):
        super().__init__(book_name="fanduel", category="sgp")


    def _map_sgp_ids(self, fanduel_data: dict) -> dict:
        return {
            f'{market_values.get("associatedMarkets")[0].get("externalMarketId")}_{runner.get("selectionId")}': {
                "market_id": main_id,
                "selection_id": runner.get("selectionId"),
                "external_id": market_values.get("associatedMarkets")[0].get("externalMarketId")
            }

            for main_id, market_values in fanduel_data.items()
            for runner in market_values.get("runners", [])
        }

    async def _runner_external_map(self, session: CurlAsyncSession) -> set:
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("additional_id_url").format(event_type=external),
                headers=self.book_data.mapping.headers,
                method=self.book_data.mapping.method
            )
            for external in FanduelMapper.EXTERNAL_MAPS.values()
        ]

        results = await asyncio.gather(*tasks)

        event_ids = set()

        for data in results:
            if not data.get("layout", {}).get("coupons"):
                continue

            for coupon_values in data.get("layout", {}).get("coupons").values():
                if coupon_values.get("display"):
                    for coupon_display in coupon_values.get("display"):
                        if not coupon_display.get("rows"):
                            continue

                        for row in coupon_display.get("rows", []):
                            if row.get("eventId"):
                                event_ids.add(row.get("eventId"))

        return event_ids

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        base_raw_stat_list = await self.api_caller(
            session=session,
            url=self.book_data.mapping.url.get("event_id_url"),
            method=self.book_data.mapping.method
        )

        if not base_raw_stat_list:
            return False

        stat_ids = set(base_raw_stat_list)
        external_ids = await self._runner_external_map(session=session)
        stat_ids.update(external_ids)

        if not stat_ids:
            return False

        raw_sgp_markets = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("sgp_markets").format(event_id=stat),
                headers=self.book_data.mapping.headers,
                method=self.book_data.mapping.method
            )
            for stat in stat_ids
        ]

        sgp_market_results = await asyncio.gather(*raw_sgp_markets)

        if not sgp_market_results:
            return False

        mapped_ids = {}

        for sgp in sgp_market_results:
            if not sgp.get("attachments", {}).get("markets"):
                continue

            fanduel_ids = self._map_sgp_ids(sgp.get("attachments", {}).get("markets"))
            mapped_ids.update(fanduel_ids)

        await redis_instance.store_data(
            key_name="fanduel_ids",
            data_to_store=mapped_ids,
            key_expiration=self.default_key_expiration
        )

        return True

if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = FanduelMapper()
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
