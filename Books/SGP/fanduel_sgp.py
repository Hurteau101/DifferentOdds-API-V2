import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


class FanduelSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="fanduel", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_data = await self._map_data()

            # Check if mapped_data is empty or contains None marketId
            if not mapped_data or any(data for data in mapped_data if data.get("marketId") is None):
                return None

            payload = self._create_payload(mapped_data)

            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("sgp_url"),
                method="POST",
                headers=self.book_data.headers,
                payload=payload
            )

            if not api_data:
                return

            number_of_legs = len(mapped_data)

            return self._extract_odds(api_data, number_of_legs)

    def _extract_odds(self, api_data: dict, leg_number: int) -> dict | None:

        odds_dict = next((
            sgp
            for bet_keys, bet_values in api_data.items()
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
        if not self.mapped_ids:
            create_sentry_message(
                tag_key="fanduel",
                tag_value="mapping_failure",
                message="No mapped IDs were found.",
                level="error"
            )

            return None

        return [
            {
                "marketId": self.mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("market_id"),
                "selectionId": self.mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("selection_id"),
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
