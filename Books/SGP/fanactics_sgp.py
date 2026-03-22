import asyncio
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
from Utils.socket_pooler import SocketHelper

_pool = SocketHelper(url="wss://sportsbook.1.betfanatics.com/sportsbook-streaming-ws", headers={
    "Accept-Encoding": "gzip,deflate",
    "Accept-Charset": "UTF-8",
    "Accept": "*/*",
    "User-Agent": "ktor-client",
})

class FanaticsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(
            request_type=SportbookRequestType.ASYNC,
            category="SGP",
            book_name="fanatics",
            retry_amount=4,
            retry_wait_interval=1,
            sgp_data=sgp_data,
            **kwargs
        )

    def _extract_odds(self, ws_response) -> dict | None:
        offer = ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {})
        if not offer:
            return None

        odds = next(iter(offer.values())).get("displayOdds", {})
        if not odds:
            return None

        american_odds = odds.get("american") or odds.get("moneyLine")

        return FanaticsSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=odds.get("decimal")
        )

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session=None):
        payload = {
            "BetslipBuilderRequest": {
                "channel": "AMELCO_TN_MASTER",
                "currency": "USD",
                "selections": [
                    {
                        "id": int(data.get("selection_id")),
                        "banker": False,
                        "eachWay": False,
                        "mostBalanced": False
                    }
                    for data in self.link_data
                ],
                "sessionToken": None
            }
        }

        data = await _pool.send(payload=payload)

        if not data:
            return None

        return self._extract_odds(data)


if __name__ == "__main__":
    sgp_data = {'book_name': 'fanatics', 'links': ['fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%224005174%22%2C%22marketId%22%3A%22540753973%22%2C%22selectionId%22%3A%221339177627%22%7D%5D%7D&deep_link_value=consume-betslip', 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%224005174%22%2C%22marketId%22%3A%22540753985%22%2C%22selectionId%22%3A%221339177687%22%7D%5D%7D&deep_link_value=consume-betslip'], 'lines': {'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%224005174%22%2C%22marketId%22%3A%22540753973%22%2C%22selectionId%22%3A%221339177627%22%7D%5D%7D&deep_link_value=consume-betslip': 3.5, 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%224005174%22%2C%22marketId%22%3A%22540753985%22%2C%22selectionId%22%3A%221339177687%22%7D%5D%7D&deep_link_value=consume-betslip': 8.5}, 'event_data': [{'market_name': 'Player Rebounds', 'selection_name': 'Cason Wallace Over 3.5'}, {'market_name': 'Player Points', 'selection_name': 'Cason Wallace Over 8.5'}]}

    async def main():
        tasks = [FanaticsSGP(sgp_data=sgp_data).run_book() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        for i, result in enumerate(results, 1):
            print(f"Result {i}: {result}")

    asyncio.run(main())