from xmlrpc.client import Boolean

import aiohttp
from Settings.book_base import SportbookRequestType
from Settings.prediction_book_base import ExchangeBookBase
import re
from datetime import datetime, timedelta
from Prediction.kalash_parse import TotalHandler, MarketHander, MoneylineHandler, SpreadHanlder, TouchdownHandler


class Kalashi(ExchangeBookBase):
    """Class for Kalashi exchange, inheriting from ExchangeBookBase."""
    # These are the sports and markets we are interested in
    SPORTS = ["KXNFLGAME", "KXNFLSPREAD", "KXMLBGAME", "KXNFLTOTAL", "KXNCAAFGAME",
              "KXNCAAFTOTAL", "KXNCAAFSPREAD", "KXNFLANYTD", "KXNFL2TD"]

    PLURAL_PLAYER_LINES = ["2td"] # Plural lines will have 1.5 as the line value instead of 0.5

    # Markets we want to process
    MARKET_HANDLERS = {
        "Total": TotalHandler,
        "Moneyline": MoneylineHandler,
        "Spread": SpreadHanlder,
        "Anytd": TouchdownHandler,
        "2td": TouchdownHandler,
    }

    def __init__(self, log_directory=None, log_name=None):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="kalashi")

    def _league_market_mapper(self, event_ticker):
        # Map event ticker to league and stat type
        stat_type = event_ticker.split("-")[0].replace("KX","")
        match = re.match(r"([A-Z]+)(TOTAL|SPREAD|GAME|ANYTD|2TD)", stat_type)
        if match:
            league, stat_type = match.groups()
            if stat_type == "GAME":
                return league, "Moneyline"

            return league, stat_type.capitalize()


    def _extract_sports(self, sports_data):
        # Extract sports tickers based on predefined sports list
        return {
            sport.get("ticker")
            for sport in sports_data.get("series", []) or []
            # if any((tag or "").lower() in Kalashi.SPORTS for tag in (sport.get("tags") or [])) and self._filter_tickers(sport.get("ticker"))
            if sport.get("ticker") in Kalashi.SPORTS
        }

    def date_checker(self, event_ticker):
        # Check if the event date is within the next 30 days
        date_portion = event_ticker.split("-")
        if len(date_portion) > 2:
            date_portion = date_portion[1]
        else:
            date_portion = date_portion[-1]

        get_date = re.match(r"^(\d{2}[A-Z]{3}\d{2})", date_portion)
        if get_date:
            date_str = get_date.group(1)
            event_date = datetime.strptime(date_str, "%y%b%d")

            now = datetime.now()
            max_date = now + timedelta(days=30)

            # Check if event date is within the next 30 days
            return now.date() <= event_date.date() <= max_date.date(), event_date.date()

        return False, None

    def _market_handler(self, market_name, market_object, series_ticker, titles, league, event_date, event_ticker, plural_player_line=False):
        if market_name not in MarketHander.get_valid_markets():
            return None

        handler_cls = Kalashi.MARKET_HANDLERS.get(market_name)
        if not handler_cls:
            return None

        # Initialize the market handler
        handler = handler_cls(
            market_name=market_name,
            market_object=market_object,
            series_ticker=series_ticker,
            titles=titles,
            league=league,
            event_date=event_date,
            event_ticker=event_ticker,
            plural_player_line=plural_player_line
        )

        # Parse and return the market data
        return handler.parse()



    async def _get_event_details(self, series_ticker, session, titles):
        # Get event details for a given series ticker
        market_information = []

        # Recursive function to loop through events with pagination
        async def loop_events(params):
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("markets_url"),
                method=self.book_data.method,
                params=params
            )

            if not api_data:
                self.file_logger.log(
                    message=f"Potential Rate Limit hit for {series_ticker} [Event Details] - No data returned",
                    level="ERROR",
                )

                return

            for market in api_data.get("markets", []):
                valid_date, event_date = self.date_checker(market.get("event_ticker"))
                league, market_name = self._league_market_mapper(market.get("event_ticker"))
                if all([market.get("status") == "active", valid_date, market_name, league, Boolean(market.get("last_price"))]):
                    market_data = self._market_handler(
                        market_name=market_name,
                        market_object=market,
                        series_ticker=series_ticker,
                        titles=titles,
                        league=league,
                        event_date=event_date,
                        event_ticker=market.get("event_ticker"),
                        plural_player_line=True if market_name in Kalashi.PLURAL_PLAYER_LINES else False
                    )

                    if market_data:
                        market_information.extend(market_data)

            cursor = api_data.get("cursor")
            if cursor:
                next_params = {
                    "limit": 200,
                    "series_ticker": series_ticker,
                    "cursor": cursor,
                }
                await loop_events(next_params)

        await loop_events({"limit": 200, "series_ticker": series_ticker})
        return market_information

    async def _get_match_title(self, series_ticker, session):
        # Get event details for a given series ticker
        market_information = {}

        # Recursive function to loop through events with pagination
        async def loop_events(params):
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("title_url"),
                method=self.book_data.method,
                params=params
            )

            if not api_data:
                self.file_logger.log(
                    message=f"Potential Rate Limit hit for {series_ticker} [Match Title] - No data returned",
                    level="ERROR",
                )

            for market in api_data.get("events", []):
                match_title = market.get("title").split(":")[0]
                if "winner" in match_title.lower():
                    match_title = match_title.replace("Winner?", "").strip()

                market_information[market.get("event_ticker")] = match_title

            cursor = api_data.get("cursor")
            if cursor:
                next_params = {
                    "limit": 200,
                    "series_ticker": series_ticker,
                    "cursor": cursor,
                }
                await loop_events(next_params)

        await loop_events({"limit": 200, "series_ticker": series_ticker})
        return market_information


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("sports_url"),
                method=self.book_data.method,
                params={
                    "category": "Sports",
                }
            )

            if not api_data:
                return None

            series_ticker = self._extract_sports(api_data)
            match_titles = [self._get_match_title(tick, session) for tick in series_ticker]

            title_results = await asyncio.gather(*match_titles)
            title_lookup = {k: v for d in title_results for k, v in d.items()}

            if not title_lookup:
                return

            event_results = [self._get_event_details(tick, session, title_lookup) for tick in series_ticker]
            event_details = await asyncio.gather(*event_results)

            if not event_details:
                return

            flatted_events = [event for sublist in event_details for event in sublist]

            if not flatted_events:
                return



if __name__ == "__main__":
    import asyncio
    kalashi = Kalashi()
    asyncio.run(kalashi.run_book())