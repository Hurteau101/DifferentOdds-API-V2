# import asyncio
# import json
# import websockets
# from Books.Bases.sgp_book_base import SGPBookBase
# from Monitoring.monitoring import create_sentry_message
# from Utils.request_caller import SportbookRequestType
#
#
# fanatics_semaphore = asyncio.Semaphore(1)
#
# class FanaticsSGP(SGPBookBase):
#
#     connection = None
#
#     def __init__(self, sgp_data: dict, **kwargs):
#         super().__init__(
#             request_type=SportbookRequestType.ASYNC,
#             category="SGP",
#             book_name="fanatics",
#             retry_amount=4,
#             retry_wait_interval=1,
#             sgp_data=sgp_data,
#             **kwargs
#         )
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
#     @SGPBookBase.ensure_link_data
#     @SGPBookBase.retry_book(is_disabled=False)
#     async def run_book(self):
#         async with fanatics_semaphore:
#
#             payload = {
#                 "BetslipBuilderRequest": {
#                     "channel": "AMELCO_TN_MASTER",
#                     "currency": "USD",
#                     "selections": [
#                         {
#                             "id": int(data.get("selection_id")),
#                             "banker": False,
#                             "eachWay": False,
#                             "mostBalanced": False
#                         }
#                         for data in self.link_data
#                     ],
#                     "sessionToken": None
#                 }
#             }
#
#             message_check = None
#
#             try:
#                 async with websockets.connect(
#                         self.book_data.url.get("main_url"),
#                         extra_headers=self.book_data.headers,
#                         ping_interval=None,
#                 ) as websocket:
#
#                     await websocket.send(json.dumps(payload))
#
#                     # timeout_seconds = 5
#
#                     while True:
#                         message = await asyncio.wait_for(websocket.recv(), timeout=30)
#                         message_check = message
#                         data = json.loads(message)
#
#
#                         odds = self._extract_odds(data)
#
#                         if odds:
#                             return odds
#                     # while True:
#                     #     message = await asyncio.wait_for(
#                     #         websocket.recv(),
#                     #         timeout=timeout_seconds
#                     #     )
#                     #
#                     #     data = json.loads(message)
#                     #
#                     #     if data.get("BetslipOfferMessage", {}) \
#                     #             .get("eventIdToSameGameParlayOffer"):
#                     #         return self._extract_odds(data)
#
#             except asyncio.TimeoutError as e:
#                 if message_check and "BetslipOfferMessage" in message_check:
#                     print("Message: ", message_check)
#                     print("Fanatics Timed Out: ", e)
#
#                 return None
#
#             except Exception as e:
#                 print('Fanatics Error: ', e)
#                 create_sentry_message(
#                     tag_key=self.book_data.name,
#                     tag_value="websockets",
#                     message=f"WS error: {e}",
#                     level="error"
#                 )
#                 return None
#
#
# if __name__ == "__main__":
#     sgp_data = {'book_name': 'fanatics', 'links': ['fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902297%22%2C%22marketId%22%3A%22524267711%22%2C%22selectionId%22%3A%221299204110%22%7D%5D%7D&deep_link_value=consume-betslip', 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902297%22%2C%22marketId%22%3A%22524267591%22%2C%22selectionId%22%3A%221299203744%22%7D%5D%7D&deep_link_value=consume-betslip']}
#
#     hardrock = FanaticsSGP(sgp_data=sgp_data)
#     data = asyncio.run(hardrock.run_book())
#     print(data)



import asyncio
import json
import websockets

from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


fanatics_semaphore = asyncio.Semaphore(1)


class FanaticsSGP(SGPBookBase):

    connection = None
    connection_lock = asyncio.Lock()

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

    @classmethod
    async def get_connection(cls, url, headers):

        current_loop = asyncio.get_running_loop()

        if (
                cls.connection
                and not cls.connection.closed
                and cls.connection_loop == current_loop
        ):
            return cls.connection

        async with cls.connection_lock:

            if (
                    cls.connection
                    and not cls.connection.closed
                    and cls.connection_loop == current_loop
            ):
                return cls.connection

            try:
                cls.connection = await websockets.connect(
                    url,
                    extra_headers=headers,
                    ping_interval=None
                )

                cls.connection_loop = current_loop

            except Exception as e:
                create_sentry_message(
                    tag_key="fanatics",
                    tag_value="websocket_connect",
                    message=f"Connection error: {e}",
                    level="error"
                )
                raise

            return cls.connection

    # @classmethod
    # async def get_connection(cls, url, headers):
    #     """Ensures only one websocket connection exists"""
    #     if cls.connection and not cls.connection.closed:
    #         return cls.connection
    #
    #     async with cls.connection_lock:
    #         if cls.connection and not cls.connection.closed:
    #             return cls.connection
    #
    #         try:
    #             cls.connection = await websockets.connect(
    #                 url,
    #                 extra_headers=headers,
    #                 ping_interval=None
    #             )
    #
    #         except Exception as e:
    #             create_sentry_message(
    #                 tag_key="fanatics",
    #                 tag_value="websocket_connect",
    #                 message=f"Connection error: {e}",
    #                 level="error"
    #             )
    #             raise
    #
    #         return cls.connection


    def _extract_odds(self, ws_response) -> dict | None:

        if not ws_response.get("BetslipOfferMessage", {}).get("eventIdToSameGameParlayOffer", {}):
            return None

        odds = next(iter(
            ws_response["BetslipOfferMessage"]["eventIdToSameGameParlayOffer"].values()
        )).get("displayOdds", {})

        american_odds = odds.get("american") or odds.get("moneyLine")

        return FanaticsSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=odds.get("decimal")
        ) if odds else None

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=False)
    async def run_book(self):

        async with fanatics_semaphore:

            websocket = await self.get_connection(
                self.book_data.url.get("main_url"),
                self.book_data.headers
            )

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

                await websocket.send(json.dumps(payload))

                while True:

                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30
                    )

                    message_check = message
                    data = json.loads(message)

                    odds = self._extract_odds(data)

                    if odds:
                        return odds

            except asyncio.TimeoutError as e:
                if message_check and "BetslipOfferMessage" in message_check:
                    print("Message:", message_check)
                    print("Fanatics Timed Out:", e)

                return None

            except websockets.ConnectionClosed:
                # Reset the connection if it's closed
                FanaticsSGP.connection = None
                FanaticsSGP.connection_loop = None
                return None

            except Exception as e:
                print("Fanatics Error:", e)

                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="websockets",
                    message=f"WS error: {e}",
                    level="error"
                )

                FanaticsSGP.connection = None
                FanaticsSGP.connection_loop = None
                return None


if __name__ == "__main__":

    sgp_data = {'book_name': 'fanatics', 'links': ['fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902261%22%2C%22marketId%22%3A%22524426307%22%2C%22selectionId%22%3A%221299589793%22%7D%5D%7D&deep_link_value=consume-betslip', 'fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223902261%22%2C%22marketId%22%3A%22524885572%22%2C%22selectionId%22%3A%221300689754%22%7D%5D%7D&deep_link_value=consume-betslip']}

    book = FanaticsSGP(sgp_data=sgp_data)
    data = asyncio.run(book.run_book())
    print(data)