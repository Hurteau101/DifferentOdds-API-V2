import aiohttp
from Settings.book_base import SportbookRequestType
from Settings.exchange_book_base import ExchangeBookBase
import re
from aiolimiter import AsyncLimiter
from datetime import datetime, timedelta

class Kalashi(ExchangeBookBase):
    """Class for Kalashi exchange, inheriting from ExchangeBookBase."""
    # SPORTS = ["baseball", "football"]
    SPORTS = {
        "baseball": ["MLB"],
        "football": ["NFL"]
    }

    MARKETS = ["TOTAL", "SPREAD", "GAME"]

    def __init__(self, log_directory=None, log_name=None):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="kalashi")
        self.read_limiter = AsyncLimiter(20, 1)
        self.invalid_requests = []

    def _regex_stats(self, stat_type, sub_title):
        line_regex = re.search(r"\d+\.\d+", sub_title)
        if not line_regex:
            return {}

        line = float(line_regex.group())
        return {
            "stat_type": stat_type,
            "line": line
        }

    def _regex_mapper(self, title, event_ticker, sub_title):
        if "GAME" in event_ticker:
            return {
                "stat_type": "Moneyline",
                "line": None
            }

        stat_type = title.split(":")[-1]
        return self._regex_stats(stat_type, sub_title)



    def _filter_tickers(self, tick):
        # Filter tickers that start with "KX" and match the league and market patterns
        if not tick.startswith("KX"):
            return False

        leagues = [league for sublist in Kalashi.SPORTS.values() for league in sublist]
        markets = Kalashi.MARKETS

        pattern = re.compile(rf"^KX(?:{'|'.join(leagues)})(?:{'|'.join(markets)})$")
        return bool(pattern.match(tick))

    def _extract_sports(self, sports_data):
        # Extract sports tickers based on predefined sports list
        return {
            sport.get("ticker")
            for sport in sports_data.get("series", []) or []
            if any((tag or "").lower() in Kalashi.SPORTS for tag in (sport.get("tags") or [])) and self._filter_tickers(sport.get("ticker"))
        }

    async def _extract_market_data(self, event_ticker, session):
        pass
        # api_data = await self.api_caller(
        #     session=session,
        #     url=self.book_data.url.get("event_url").format(event_ticker=event_ticker),
        #     method=self.book_data.method,
        # )
        #
        # print(api_data)

        # if not api_data:
        #     self.invalid_requests.append(event_ticker)

    def check_date(self, event_ticker):
        date_portion = event_ticker.split("-")
        if len(date_portion) > 2:
            date_portion = date_portion[1]
        else:
            date_portion = date_portion[-1]

        get_date = re.match(r"^(\d{2}[A-Z]{3}\d{2})", date_portion)
        if get_date:
            date_str = get_date.group(1)
            event_date = datetime.strptime(date_str, "%y%b%d")

            if event_date < datetime.now() - timedelta(days=30):
                return True


    async def _get_event_details(self, series_ticker, session):
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
                print(series_ticker)

            for market in api_data.get("markets", []):
                event_ticker = market.get("event_ticker")
                if self.check_date(event_ticker):
                    market_information.append({
                        "ticker": market.get("ticker"),
                        "event_ticker": event_ticker,
                        "yes_sub_title": market.get("yes_sub_title", {}),
                        "no_sub_title": market.get("no_sub_title", {}),
                    })

            # else:
            #     for event in api_data.get("markets", []):
            #         if self.check_date(event.get("event_ticker")):
            #             market_information.append(event.get("ticker"))

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
                self._api_call_log("kalashi")
                return None

            series_ticker = self._extract_sports(api_data)


            event_results = [self._get_event_details(tick, session) for tick in series_ticker]
            event_details = await asyncio.gather(*event_results)
            flatted_events = [event for sublist in event_details for event in sublist]

            with open("kalashi_markets.json", "w") as f:
                import json
                json.dump(flatted_events, f, indent=4)

            # # print(flatted_events)
            # print(len(flatted_events))



            # flatted_events = [event for sublist in event_details for event in sublist]
            # print(len(flatted_events))
            # 2014

            # for event in flatted_events:
            #     await self._extract_market_data(event, session)

            #
            # market_results = [self._extract_market_data(event, session) for event in flatted_events]
            # market_details = await asyncio.gather(*market_results)
            # print(len(self.invalid_requests))



            # Get Series
            # Get Markets


            #
            # import json
            # with open("kalashi.json", "w") as f:
            #     json.dump(api_data, f, indent=4)







if __name__ == "__main__":
    import asyncio
    kalashi = Kalashi()
    asyncio.run(kalashi.run_book())
