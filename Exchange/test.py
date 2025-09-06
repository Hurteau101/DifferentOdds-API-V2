# async def _get_event_details(self, series_ticker, session):
#     # Get event details for a given series ticker
#     market_information = set()
#
#     # Recursive function to loop through events with pagination
#     async def loop_events(params):
#         api_data = await self.api_caller(
#             session=session,
#             url=self.book_data.url.get("events_url"),
#             method=self.book_data.method,
#             params=params
#         )
#
#         for event in api_data.get("events", []):
#             if self.check_date(event.get("event_ticker")):
#                 market_information.add(event.get("event_ticker"))
#
#         cursor = api_data.get("cursor")
#         if cursor:
#             next_params = {
#                 "limit": 200,
#                 "series_ticker": series_ticker,
#                 "cursor": cursor,
#             }
#             await loop_events(next_params)
#
#     await loop_events({"limit": 200, "series_ticker": series_ticker})
#     return market_information

# async def _get_event_details(self, series_ticker, session):
#     # Get event details for a given series ticker
#     market_information = set()
#
#     # Recursive function to loop through events with pagination
#     async def loop_events(params):
#         api_data = await self.api_caller(
#             session=session,
#             url=self.book_data.url.get("events_url"),
#             method=self.book_data.method,
#             params=params
#         )
#
#         for event in api_data.get("events", []):
#             if self.check_date(event.get("event_ticker")):
#                 market_information.add(event.get("event_ticker"))
#
#         cursor = api_data.get("cursor")
#         if cursor:
#             next_params = {
#                 "limit": 200,
#                 "series_ticker": series_ticker,
#                 "cursor": cursor,
#             }
#             await loop_events(next_params)
#
#     await loop_events({"limit": 200, "series_ticker": series_ticker})
#     return market_information