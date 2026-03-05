import asyncio
import json
import websockets
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


fanatics_semaphore = asyncio.Semaphore(1)

class FanaticsSGP(SGPBookBase):

    connection = None

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
        if not ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {}):
            return None

        odds = next(iter(ws_response["BetslipOfferMessage"]["eventIdToSameGameParlayOffer"].values())).get(
            "displayOdds", {})

        american_odds = odds.get("american") or odds.get("moneyLine")

        return FanaticsSGP.return_odds(american_odds=american_odds,
                                      decimal_odds=odds.get("decimal")) if odds else None

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=False)
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
                ) as websocket:

                    await websocket.send(json.dumps(payload))

                    # timeout_seconds = 5

                    while True:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        message_check = message
                        data = json.loads(message)


                        odds = self._extract_odds(data)

                        if odds:
                            return odds
                    # while True:
                    #     message = await asyncio.wait_for(
                    #         websocket.recv(),
                    #         timeout=timeout_seconds
                    #     )
                    #
                    #     data = json.loads(message)
                    #
                    #     if data.get("BetslipOfferMessage", {}) \
                    #             .get("eventIdToSameGameParlayOffer"):
                    #         return self._extract_odds(data)

            except asyncio.TimeoutError as e:
                if message_check and "BetslipOfferMessage" in message_check:
                    print("Message: ", message_check)
                    print("Fanatics Timed Out: ", e)

                return None

            except Exception as e:
                print('Fanatics Error: ', e)
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="websockets",
                    message=f"WS error: {e}",
                    level="error"
                )
                return None


if __name__ == "__main__":
    sgp_data = {'book_name': 'fanatics', 'links': ['fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902297%22%2C%22marketId%22%3A%22524267711%22%2C%22selectionId%22%3A%221299204110%22%7D%5D%7D&deep_link_value=consume-betslip', 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902297%22%2C%22marketId%22%3A%22524267591%22%2C%22selectionId%22%3A%221299203744%22%7D%5D%7D&deep_link_value=consume-betslip']}

    hardrock = FanaticsSGP(sgp_data=sgp_data)
    data = asyncio.run(hardrock.run_book())
    print(data)