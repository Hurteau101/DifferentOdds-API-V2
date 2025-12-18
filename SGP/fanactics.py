import json
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase
import websockets
import asyncio

class Fanatics_SGP(SGPBookBase):
    def __init__(self, links, **kwargs):
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="fanatics_sgp.log", sportsbook_name="fanatics", links=links, decode_url=True, **kwargs)

    @SGPBookBase.require_link_data
    async def run_book(self):
        async with websockets.connect(self.book_data.url.get("main_url"), additional_headers=self.book_data.headers) as websocket:
            payload = {
                "BetslipBuilderRequest": {
                    "channel": "AMELCO_TN_MASTER",
                    "currency": "USD",
                    "selections": [
                        {"id": int(data.get("bet_id")), "banker": False, "eachWay": False, "mostBalanced": False}
                        for data in self.link_data
                    ],
                    "sessionToken": None
                }
            }
            await websocket.send(json.dumps(payload))
            message = await websocket.recv()
            try:
                received_data = json.loads(message)
            except json.JSONDecodeError:
                self.file_logger.log(
                    sportsbook="fanatics",
                    message="Failed to decode JSON response",
                    level="ERROR",
                )
                return None
            except Exception as e:
                self.file_logger.log(
                    sportsbook="fanatics",
                    message=f"Unexpected error: {e}",
                    level="ERROR",
                )
                return None

            return self._extract_odds(received_data)

    def _extract_odds(self, ws_response):
        if not ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {}):
            return None

        odds = next(iter(ws_response["BetslipOfferMessage"]["eventIdToSameGameParlayOffer"].values())).get("displayOdds", {})
        if not odds:
            return None

        return {
            "american": float(odds.get("moneyLine")),
            "decimal": float(odds.get("decimal")),
        }


if __name__ == "__main__":
    test_links = [
        "fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%222404247%22%2C%22marketId%22%3A%22365254917%22%2C%22selectionId%22%3A%22915694988%22%7D%5D%7D&",
"fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%222404247%22%2C%22marketId%22%3A%22365254917%22%2C%22selectionId%22%3A%22915694968%22%7D%5D%7D&"
    ]
    fanduel_sgp = Fanatics_SGP(test_links)
    odds = asyncio.run(fanduel_sgp.run_book())
    print(odds)
