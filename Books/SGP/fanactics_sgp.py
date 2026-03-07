import asyncio
import json
import websockets

from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


fanatics_semaphore = asyncio.Semaphore(1)


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
    async def run_book(self):
        async with fanatics_semaphore:
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

            message_check = None

            try:
                async with websockets.connect(
                    self.book_data.url.get("main_url"),
                    extra_headers=self.book_data.headers,
                    ping_interval=None,
                    open_timeout=10,
                    close_timeout=5,
                ) as websocket:

                    await websocket.send(json.dumps(payload))

                    for _ in range(5):
                        message = await asyncio.wait_for(websocket.recv(), timeout=8)
                        message_check = message

                        try:
                            data = json.loads(message)
                        except json.JSONDecodeError:
                            continue

                        odds = self._extract_odds(data)
                        if odds:
                            return odds

                    return None

            except asyncio.TimeoutError:
                if message_check:
                    print("Fanatics timeout after receiving:", message_check)
                return None

            except websockets.ConnectionClosed as e:
                print("Fanatics connection closed:", e)
                return None

            except Exception as e:
                print("Fanatics Error:", e)
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="websockets",
                    message=f"WS error: {e}",
                    level="error"
                )
                return None


if __name__ == "__main__":
    sgp_data = {
        'book_name': 'fanatics',
        'links': [
            'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902261%22%2C%22marketId%22%3A%22524426307%22%2C%22selectionId%22%3A%221299589793%22%7D%5D%7D&deep_link_value=consume-betslip',
            'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902261%22%2C%22marketId%22%3A%22524885572%22%2C%22selectionId%22%3A%221300689754%22%7D%5D%7D&deep_link_value=consume-betslip'
        ]
    }

    book = FanaticsSGP(sgp_data=sgp_data)
    data = asyncio.run(book.run_book())
    print(data)