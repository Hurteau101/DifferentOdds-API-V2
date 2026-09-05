import asyncio
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession

class FanduelSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="fanduel", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session) -> dict | None:
        mapped_data = await self._map_data()

        # Check if mapped_data is empty or contains None marketId
        if not mapped_data or any(data for data in mapped_data if data.get("marketId") is None):
            return None

        payload = self._create_payload(mapped_data)

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            default_header_override=["Accept"],
            json=payload,
        )

        if not api_data:
            return None

        number_of_legs = len(mapped_data)

        return self._extract_odds(api_data, number_of_legs)

    def _extract_odds(self, api_data: dict, leg_number: int) -> dict | None:
        odds_dict = next((
            sgp
            for bet_keys, bet_values in api_data.items()
            if isinstance(bet_values, list)
            for sgp in bet_values
            if sgp.get("legCombinations")
               and len(sgp.get("legCombinations")) == leg_number
               and sgp.get("winAvgOdds")
        ), None)

        if not odds_dict:
            return None

        return FanduelSGP.return_odds(
            american_odds=odds_dict.get("winAvgOdds").get("americanDisplayOdds", {}).get("americanOdds"),
            decimal_odds=odds_dict.get("winAvgOdds").get("decimalDisplayOdds", {}).get("decimalOdds")
        )

    async def _map_data(self) -> list | None:
        """ Map the marketID from the links to the actual marketId using Redis. Due to links being external market IDs"""
        mapped_ids = await self.mapper_redis_manager.get_data(key_name="fanduel_ids")

        if not mapped_ids:
            return None

        return [
            {
                "marketId": mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("market_id"),
                "selectionId": mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("selection_id"),
            }
            for data in self.link_data
        ]

    def _create_payload(self, payload_data):
        return {
            "betLegs": [
                {
                    "legType": "SIMPLE_SELECTION",
                    "betRunners": [
                        {
                            "runner": {
                                "marketId": str(leg.get("marketId")),
                                "selectionId": int(leg.get("selectionId")),
                            }
                        }
                    ]
                }

                for leg in payload_data
            ]
        }


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {'book_name': 'fanduel', 'links': [
                "https://sportsbook.blue_book.com/addToBetslip?marketId=42.604449122&selectionId=72268406",
                "https://sportsbook.blue_book.com/addToBetslip?marketId=42.604449172&selectionId=79285407"
                ]
            }

            book = FanduelSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())



# 294