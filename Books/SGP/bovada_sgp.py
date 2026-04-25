import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from External_Book_Mapping.SGP.bovada_mapper import BovadaMapper
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class BovadaSGP(SGPBookBase):
    def __init__(self, mapped_ids_redis_instance, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="bovada",
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)


    async def _get_mapped_ids(self):
        async with aiohttp.ClientSession() as session:
            redis_instance = RedisAsyncManager(database=2)
            mapper = BovadaMapper()
            mapped_ids = await mapper.run_scheduler(session=session, redis_instance=redis_instance)
            return mapped_ids


    async def _create_param_string(self) -> list | None:
        """Creates params for API call"""
        # mapped_ids = await self.load_mapped_ids(key_name="bovada_ids")
        mapped_ids = await self._get_mapped_ids()

        if not mapped_ids:
            return None

        additional_data = self.sgp_data.get("event_data", [])
        merged_data = [mapped | additional for mapped, additional in zip(self.link_data, additional_data)]

        outcome_ids = []

        for index, merged in enumerate(merged_data, start=1):
            found = mapped_ids.get(merged.get("event_id", '').lower())
            if not found:
                continue

            outcome_id = found.get(merged.get("market_name", '').lower(), {}).get(
                merged.get("selection_name", '').lower())

            if outcome_id:
                outcome_ids.append(("outcomeId", f"A:{outcome_id}"))
                # outcome_ids.append(f"A:{outcome_id}{index}")

        if len(outcome_ids) != len(self.link_data):
            return None

        return outcome_ids



    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        params = await self._create_param_string()
        if not params:
            return None

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method=self.book_data.method,
            headers=self.book_data.headers,
            params=params
        )

        if not api_data:
            return

        sgp_dict = next((
            bet
            for api in api_data.get("bets", {}).values()
            for bet in api
            if bet.get("description", '').lower() == "same game parlay bet"
        ), {})

        if sgp_dict.get("numWays") !=  len(self.links):
            return None

        american_odds = sgp_dict.get("totalPriceFormattedMap", {}).get("AMERICAN")

        if not american_odds:
            return None

        return BovadaSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=sgp_dict.get("totalPriceFormattedMap", {}).get("DECIMAL")
        )


if __name__ == "__main__":
    async def main():
        async with aiohttp.ClientSession() as session:
            sgp_data = {
                'book_name': 'bovada',
                'links': [
                    "https://www.bovada.lv/sports/basketball/nba/denver-nuggets-minnesota-timberwolves-202604252030",
                    "https://www.bovada.lv/sports/basketball/nba/denver-nuggets-minnesota-timberwolves-202604252030",
                ],
                'event_data': [
                    {'market_name': 'Player Assists', 'selection_name': 'Christian Braun Under 1.5'},
                    {'market_name': 'Total Points', 'selection_name': 'Under 230.5'}
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            book = BovadaSGP(mapped_ids_redis_instance=redis_mapped, sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)


    asyncio.run(main())

