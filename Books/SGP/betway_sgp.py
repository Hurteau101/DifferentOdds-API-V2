import asyncio

import aiohttp
from aiohttp import payload

from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType


class BetwaySGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="betway", sgp_data={}, **kwargs)

    async def _map_data(self, additional_data: list):
        mapped_ids = await self.load_mapped_ids(key_name="betway_mapped_ids")

        if not mapped_ids:
            return

        for data in additional_data:
            event_name = data.get("event_name")
            market_name = data.get("market_name").lower()
            selection = data.get("selection").lower() if isinstance(data.get("selection"), str) else data.get("selection")

            split_event_name = event_name.split(" vs ")
            sorted_event_name = " vs ".join(sorted(split_event_name)).lower()

            print("Event Name: ", sorted_event_name)
            print("Market Name: ", market_name)
            print("Selection: ", selection)




    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            additional_data = self.extras.get("additional_data")

            valid_input = all(
                all(data.get(key) for key in ("event_name", "market_name", "selection"))
                for data in additional_data
            )

            mapped_data = self._map_data(additional_data=additional_data)

if __name__ == "__main__":
    book = BetwaySGP(additional_data=[
        {"event_name": "Boston Celtics vs Charlotte Hornets", "market_name": "Total Points",
         "selection": "Under 218.5"},
        {"event_name": "Boston Celtics vs Charlotte Hornets", "market_name": "Total Points", "selection": "Over 224.5"}
    ])
    data = asyncio.run(book.run_book())
    print(data)