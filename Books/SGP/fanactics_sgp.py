import asyncio
import json
import websockets
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


class FanaticsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="fanatics", sgp_data=sgp_data, **kwargs)


    @SGPBookBase.ensure_link_data
    async def run_book(self):
        async with websockets.connect(self.book_data.url.get("main_url"),
                                      additional_headers=self.book_data.headers) as websocket:
            payload = {
                "BetslipBuilderRequest": {
                    "channel": "AMELCO_TN_MASTER",
                    "currency": "USD",
                    "selections": [
                        {"id": int(data.get("selection_id")), "banker": False, "eachWay": False, "mostBalanced": False}
                        for data in self.link_data
                    ],
                    "sessionToken": None
                }
            }


            await websocket.send(json.dumps(payload))
            message = await websocket.recv()
            try:
                received_data = json.loads(message)
            except Exception as e:
                create_sentry_message(
                    tag_key="fanactics",
                    tag_value="websockets",
                    message=f"There was an error with the websocket {e}",
                    level="error"
                )
                return None

            return self._extract_odds(received_data)

    def _extract_odds(self, ws_response) -> dict | None:
        if not ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {}):
            return None

        odds = next(iter(ws_response["BetslipOfferMessage"]["eventIdToSameGameParlayOffer"].values())).get(
            "displayOdds", {})

        return FanaticsSGP.return_odds(american_odds=odds.get("american"),
                                      decimal_odds=odds.get("decimal")) if odds else None


