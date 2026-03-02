# import asyncio
# import json
# import websockets
# from Books.Bases.sgp_book_base import SGPBookBase
# from Monitoring.monitoring import create_sentry_message
# from Utils.request_caller import SportbookRequestType
#
#
# class FanaticsSGP(SGPBookBase):
#     def __init__(self, sgp_data: dict, **kwargs):
#         super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="fanatics", sgp_data=sgp_data, **kwargs)
#
#
#     @SGPBookBase.ensure_link_data
#     async def run_book(self):
#         async with websockets.connect(self.book_data.url.get("main_url"),
#                                       extra_headers=self.book_data.headers) as websocket:
#             payload = {
#                 "BetslipBuilderRequest": {
#                     "channel": "AMELCO_TN_MASTER",
#                     "currency": "USD",
#                     "selections": [
#                         {"id": int(data.get("selection_id")), "banker": False, "eachWay": False, "mostBalanced": False}
#                         for data in self.link_data
#                     ],
#                     "sessionToken": None
#                 }
#             }
#
#
#             await websocket.send(json.dumps(payload))
#             message = await websocket.recv()
#             try:
#                 received_data = json.loads(message)
#             except Exception as e:
#                 create_sentry_message(
#                     tag_key=self.book_data.name,
#                     tag_value="websockets",
#                     message=f"There was an error with the websocket {e}",
#                     level="error"
#                 )
#                 return None
#
#             return self._extract_odds(received_data)
#
#     def _extract_odds(self, ws_response) -> dict | None:
#         if not ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {}):
#             return None
#
#         odds = next(iter(ws_response["BetslipOfferMessage"]["eventIdToSameGameParlayOffer"].values())).get(
#             "displayOdds", {})
#
#         american_odds = odds.get("american") or odds.get("moneyLine")
#
#         return FanaticsSGP.return_odds(american_odds=american_odds,
#                                       decimal_odds=odds.get("decimal")) if odds else None
#
#


import asyncio
import json
import websockets
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType

class FanaticsSGPConnection:
    def __init__(self, url: str, headers: dict):
        self.url = url
        self.headers = headers
        self.websocket = None
        self.lock = asyncio.Lock()
        self.connected = asyncio.Event()
        self.reader_task = None
        self.response_queue = asyncio.Queue()

    async def connect(self):
        async with self.lock:

            # Check if already connected
            if self.websocket is not None:
                return

            # Create a new websocket connection
            self.websocket = await websockets.connect(
                self.url,
                extra_headers=self.headers,
                ping_interval=None,
                open_timeout=20,
                close_timeout=10
            )

            self.connected.set()
            self.reader_task = asyncio.create_task(self._reader())

    async def close(self):
        async with self.lock:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
                self.connected.clear()

    async def _reader(self):
        """
        Background task that continuously reads messages and pushes them into a queue.
        """
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.response_queue.put(data)
                except Exception:
                    pass
        except Exception:
            self.connected.clear()
            self.websocket = None

    async def send_request(self, payload: dict) -> dict | None:
        """
        Sends a request and waits for the next response.
        """
        # Ensure connection exists
        if not self.connected.is_set():
            await self.connect()

        await self.websocket.send(json.dumps(payload))

        # Wait for response
        response = await self.response_queue.get()
        return response
fanatics_semaphore = asyncio.Semaphore(3)
class FanaticsSGP(SGPBookBase):

    connection = None

    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(
            request_type=SportbookRequestType.ASYNC,
            category="SGP",
            book_name="fanatics",
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

            try:
                async with websockets.connect(
                        self.book_data.url.get("main_url"),
                        extra_headers=self.book_data.headers,
                        ping_interval=None,
                ) as websocket:

                    await websocket.send(json.dumps(payload))

                    timeout_seconds = 5

                    while True:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=timeout_seconds
                        )

                        data = json.loads(message)

                        if data.get("BetslipOfferMessage", {}) \
                                .get("eventIdToSameGameParlayOffer"):
                            return self._extract_odds(data)

            except asyncio.TimeoutError:
                return None

            except Exception as e:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="websockets",
                    message=f"WS error: {e}",
                    level="error"
                )
                return None

    # @SGPBookBase.ensure_link_data
    # async def run_book(self):
    #
    #     if FanaticsSGP.connection is None:
    #         FanaticsSGP.connection = FanaticsSGPConnection(
    #             self.book_data.url.get("main_url"),
    #             self.book_data.headers
    #         )
    #         await FanaticsSGP.connection.connect()
    #
    #     payload = {
    #         "BetslipBuilderRequest": {
    #             "channel": "AMELCO_TN_MASTER",
    #             "currency": "USD",
    #             "selections": [
    #                 {
    #                     "id": int(data.get("selection_id")),
    #                     "banker": False,
    #                     "eachWay": False,
    #                     "mostBalanced": False
    #                 }
    #                 for data in self.link_data
    #             ],
    #             "sessionToken": None
    #         }
    #     }
    #
    #     try:
    #         received_data = await FanaticsSGP.connection.send_request(payload)
    #         print("Receieved Data", received_data)
    #         print(self.link_data)
    #     except Exception as e:
    #         create_sentry_message(
    #             tag_key=self.book_data.name,
    #             tag_value="websockets",
    #             message=f"Persistent WS error: {e}",
    #             level="error"
    #         )
    #         return None
    #
    #     return self._extract_odds(received_data)


if __name__ == "__main__":
    sgp_data = {'book_name': 'fanatics', 'links': ['fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223872927%22%2C%22marketId%22%3A%22520505286%22%2C%22selectionId%22%3A%221290015014%22%7D%5D%7D&deep_link_value=consume-betslip', 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223872927%22%2C%22marketId%22%3A%22520450712%22%2C%22selectionId%22%3A%221289885197%22%7D%5D%7D&deep_link_value=consume-betslip']}

    hardrock = FanaticsSGP(sgp_data=sgp_data)
    data = asyncio.run(hardrock.run_book())
    print(data)