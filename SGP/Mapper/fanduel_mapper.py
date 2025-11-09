import aiohttp
import asyncio
from Redis.redis_manager import RedisManager
from Settings.sgp_mapper_base import SGPMapperBase
from Settings.book_base import SportbookRequestType

class Fanduel_Mapper(SGPMapperBase):
    # To find external IDs on fanduel, go to "All Sports" and click on the sport and you will see the network call
    # ex. https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=SPORT&eventTypeId=7524&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FPhoenix

    EXTERNAL_MAPS = {
        "hockey": 7524,
        "baseball": 7511,
        "basketball": 7522,
        "football": 6423
    }

    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="fanduel", log_directory="SGP Mapper Logs", log_name="fanduel_mapper.log")

    def _map_sgp_ids(self, fanduel_data):
        return {
            f'{market_values.get("associatedMarkets")[0].get("externalMarketId")}_{runner.get("selectionId")}': {
                "market_id": main_id,
                "selection_id": runner.get("selectionId"),
                "external_id": market_values.get("associatedMarkets")[0].get("externalMarketId")
            }

            for main_id, market_values in fanduel_data.items()
            for runner in market_values.get("runners", [])
        }

    async def _runner_external_map(self, session):
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.url.get("additional_id_url").format(event_type=external),
                headers=self.book_data.headers,
                method=self.book_data.method
            )
            for external in Fanduel_Mapper.EXTERNAL_MAPS.values()
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


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            base_raw_stat_list = await self.api_caller(
                session=session,
                url=self.book_data.url.get("event_id_url"),
                method=self.book_data.method
            )

            api_data = self.check_api_response(sportsbook="fanduel", results=base_raw_stat_list)
            if not api_data:
                return

            stat_ids = set(api_data.get("data", []))
            external_ids = await self._runner_external_map(session=session)
            stat_ids.update(external_ids)

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("sgp_markets").format(event_id=stat),
                    headers=self.book_data.headers,
                    method=self.book_data.method
                )
                for stat in stat_ids
            ]

            results = await asyncio.gather(*tasks)
            sgp_data = self.check_api_response(sportsbook="fanduel", results=results)
            if not sgp_data:
                return

            mapped_ids = {}

            for sgp in sgp_data:
                if not sgp.get("attachments", {}).get("markets"):
                    continue


                fanduel_ids = self._map_sgp_ids(sgp.get("attachments", {}).get("markets"))
                mapped_ids.update(fanduel_ids)

            if mapped_ids:
                redis = RedisManager(db=self.redis_db)
                await redis.store_data(
                    key_name="fanduel_ids",
                    data_to_store=mapped_ids,
                    key_expiration=self.key_expiration
                )


if __name__ == "__main__":
    fanduel_instance = Fanduel_Mapper()
    asyncio.run(fanduel_instance.run_book())