import asyncio
import re
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager



class BetwaySGP(SGPBookBase):
    def __init__(self, mapped_ids_redis_instance, **kwargs):
        super().__init__(category="SGP", book_name="betway",
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)

    async def _get_outcome_ids(self, additional_list: list) -> list | None:
        mapped_ids = await self.load_mapped_ids(key_name="betway_mapped_ids")

        if not mapped_ids:
            return None

        pattern = re.compile(r"event/(\d+)")
        event_id = next((
            found_id.group(1)
            for link in self.links
            if (found_id := pattern.search(link))
        ), None)

        if not event_id:
            return None

        outcome_ids = []

        for additional in additional_list:
            market_name = additional["market_name"]
            selection = additional["selection_name"]
            generate_key = "_".join([market_name, selection]).lower().replace(" ", "_")

            found_mapping = mapped_ids.get(event_id, {}).get(generate_key)

            if found_mapping:
                outcome_ids.append(found_mapping)

        if len(outcome_ids) != len(additional_list):
            return None

        return outcome_ids

    async def _extract_odds(self, outcome_ids: list, session: CurlAsyncSession):
        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            json={
                "BrandId": 3,
                "LanguageId": 25,
                "ClientTypeId": 2,
                "JurisdictionId": 2,
                "ClientIntegratorId": 1,
                "Selections": outcome_ids,
                "Rewards": []
            }
        )

        if not api_data or not isinstance(api_data, dict) or api_data.get("UnavailableOutcomeIds"):
            return None

        bets = api_data.get("Bets")

        if not bets or not isinstance(bets, list):
            return None

        selection_group = bets[0]
        decimal_odds = selection_group.get("BetPrice", {}).get("dec")

        selections = selection_group.get("Selections", [])

        if len(outcome_ids) != len(selections) or not decimal_odds:
            return None

        american_odds = self.convert_decimal_to_american(float(decimal_odds))

        return BetwaySGP.return_odds(
            american_odds=american_odds,
            decimal_odds=float(decimal_odds)
        )

    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        additional_data = self.sgp_data.get("event_data", [])

        valid_input = all(
            key in data
            for data in additional_data
            for key in ("market_name", "selection_name")
        ) and bool(self.links)


        if not valid_input:
            return None

        outcome_ids = await self._get_outcome_ids(additional_list=additional_data)
        if not outcome_ids:
            return

        return await self._extract_odds(outcome_ids=outcome_ids, session=session)


#### CHECK OTHER MAPPING TO ENSURE ERRORS ARE SENT

if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {
                'book_name': 'betway',
                'links': [
                    "https://{state}.betway.com/sports/event/16902972",
                    "https://{state}.betway.com/sports/event/16902972",
                ],
                'event_data': [
                    {'market_name': 'Moneyline', 'selection_name': 'Chicago Cubs'},
                    {'market_name': 'Total Runs', 'selection_name': 'Over 7.5'}
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            book = BetwaySGP(sgp_data=sgp_data, mapped_ids_redis_instance=redis_mapped)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())



    # sgp_data = {
    #     'book_name': 'betmgm',
    #     'links': ["https://{state}.betway.com/sports/event/16447138",
    #               "https://{state}.betway.com/sports/event/16447138"]
    # }
    #
    # additional_data = [
    #     {"market_name": "Player Points", "selection": "PJ Washington Over 12.5"},
    #     {"market_name": "Player Points", "selection": "Jayson Tatum Over 12.5"}
    # ]
    #
    # book = BetwaySGP(sgp_data=sgp_data, additional_data=additional_data)
    # data = asyncio.run(book.run_book())
    # print(data)
