import asyncio
import re

import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class BovadaSGP(SGPBookBase):
    def __init__(self, mapped_ids_redis_instance, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="bovada",
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)

    def _verify_line(self, selection_list: list, current_entries: dict):
        selections = {
            selection.get("outcomeId", ''): selection.get("points")
            for selection in selection_list
        }

        return current_entries == selections


    async def _create_param_string(self) -> dict | None:
        """Creates params for API call"""
        mapped_ids = await self.load_mapped_ids(key_name="bovada_ids")

        if not mapped_ids:
            return None

        additional_data = self.sgp_data.get("event_data", [])
        merged_data = [mapped | additional for mapped, additional in zip(self.link_data, additional_data)]

        sgp_data = {
            "outcome_ids": [],
            "lines": {}
        }

        for index, merged in enumerate(merged_data, start=1):
            found = mapped_ids.get(merged.get("event_id", '').lower())
            if not found:
                continue

            outcome_found = found.get(merged.get("market_name", '').lower(), {}).get(
                merged.get("selection_name", '').lower())

            if not outcome_found:
                continue

            line = outcome_found.get("line")
            # print(line)
            # print(merged)
            # if line:
            #     print(line)
            #     merged_line = float(merged.get("line", 0))
            #
            #     if float(merged.get("line")) != merged_line:
            #         continue

            outcome_id = outcome_found.get("outcome_id")

            if outcome_id:
                sgp_data["outcome_ids"].append(("outcomeId", f"A:{outcome_id}"))
                sgp_data["lines"].update({outcome_id: float(line) if line else 0.0})


        if len(sgp_data["outcome_ids"]) != len(self.link_data):
            return None

        return sgp_data



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
            params=params.get("outcome_ids", []),
            ssl=False
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


        has_same_lines = self._verify_line(selection_list=api_data.get("selections", {}).get("selection"), current_entries=params.get("lines", {}))

        if not has_same_lines:
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
                "book_name": "bovada",
                "links": [
                    "https://www.bovada.lv/sports/baseball/mlb/seattle-mariners-cleveland-guardians-202606261910",
                    "https://www.bovada.lv/sports/baseball/mlb/seattle-mariners-cleveland-guardians-202606261910",
                ],
                'event_data': [
                    {'market_name': 'Moneyline', 'selection_name': 'Cleveland Guardians'},
                    {'market_name': 'Total Runs', 'selection_name': 'Under 7.5'}
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            book = BovadaSGP(mapped_ids_redis_instance=redis_mapped, sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)


    asyncio.run(main())

