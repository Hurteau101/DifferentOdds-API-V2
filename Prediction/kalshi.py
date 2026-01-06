import os
import time
import aiohttp
import asyncio
from aiolimiter import AsyncLimiter
from dotenv import load_dotenv
from tenacity import retry, retry_if_result, wait_exponential, stop_after_attempt
from datetime import datetime, timedelta, timezone
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.Prediction_Settings.prediction_model import Game, Order
from Prediction.Helper.handler import make_handler
from Settings.book_base import SportbookRequestType
from Settings.Prediction_Settings.prediction_book_base import PredictionBookBase
import re
from Settings.proxy_manger import ProxyManager


def is_rate_limited(result: dict) -> bool:
    """Check if the API response indicates a rate limit error."""
    return (
        result is not None
        and result.get("error", {}).get("status") == 429
    )


class Kalshi(PredictionBookBase):
    SPORTS = {
        "football": {
            # "leagues": ["NFL", "NCAAF"],
            # "markets": ["KX_GAME", "KX_SPREAD", "KX_TOTAL", "KX_ANYTD", "KX_2TD"],
            "leagues": ["NFL"],
            "markets": ["KX_GAME"],
        },

        # "basketball": {
        #     "leagues": ["NCAAMB", "NCAAWB", "NBA", "WNBA"],
        #     "markets": ["KX_GAME", "KX_SPREAD", "KX_TOTAL", "KX_PTS", "KX_AST", "KX_REB", "KX_3PT", "KX_2D"],
        # },
        # "hockey": {
        #     "leagues": ["NHL"],
        #     "markets": ["KX_GAME", "KX_SPREAD", "KX_TOTAL", "KX_FIRSTGOAL", "KX_GOAL", "KX_PTS", "KX_AST"],
        # }
    }

    MAPPER = {
        "KX_GAME": {
            "kalshi_market_name": "Moneyline",
        },
        "KX_SPREAD": {
            "kalshi_market_name": "Spread",
        },
        "KX_TOTAL": {
            "kalshi_market_name": "Total Points",
            "actual_name": "Total"
        },
        "KX_ANYTD": {
            "kalshi_market_name": "Anytime Touchdown Scorer",
        },
        "KX_2TD": {
            "kalshi_market_name": "Two or More Touchdowns Scorer",
            "actual_name": "2TD+"
        },
        "KX_PTS": {
            "kalshi_market_name": "Points",
        },
        "KX_AST": {
            "kalshi_market_name": "Assists",
        },
        "KX_REB": {
            "kalshi_market_name": "Rebounds",
        },
        "KX_3PT": {
            "kalshi_market_name": "Three Pointers",
            "actual_name": "3PT Made"
        },
        "KX_2D": {
            "kalshi_market_name": "Double Doubles",
        },
        "KX_FIRSTGOAL": {
            "kalshi_market_name": "First Goal Scorer",
        },
        "KX_GOAL": {
            "kalshi_market_name": "Anytime Goal",
        },
    }

    def __init__(self, log_directory=None, log_name=None):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="kalshi")
        self.rate_limiter = AsyncLimiter(20, 1)  # 20 Requests per second
        load_dotenv()
        proxies = os.getenv("KALSHI_PROXIES")
        self.proxy_list = proxies.split(",") if proxies else []

    @staticmethod
    def within_date_range(date_limit: int, date_value: str):
        """Check if the given date is within the specified date limit from today."""
        if not date_limit or not date_value:
            raise ValueError("Both date_limit and date_str must be provided")

        if isinstance(date_value, str):
            date_obj = datetime.fromisoformat(
                date_value.replace("Z", "+00:00")
            )
        elif isinstance(date_value, datetime):
            date_obj = date_value.astimezone(timezone.utc)
        else:
            raise ValueError("date_str must be a datetime or ISO string")

        game_date = date_obj.date()
        today = datetime.now(timezone.utc).date()
        cutoff_max = today + timedelta(days=date_limit)

        return cutoff_max >= game_date >= today

    @retry(
        retry=retry_if_result(is_rate_limited),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        stop=stop_after_attempt(5),
    )
    async def call_with_retry(self, session: aiohttp.ClientSession, url: str, method: str, params: dict):
        """Make an API call with rate limiting and retry on rate limit errors."""
        proxy_manager = ProxyManager(self.api_caller, proxies=self.proxy_list)
        return await proxy_manager.proxy_caller_async(
            session=session,
            url=url,
            method=method,
            sportsbook="kalshi",
            params=params,
            headers={},
            avoid_single_log=True
        )


        # async with self.rate_limiter:
        #     return await self.api_caller(
        #         session=session,
        #         url=url,
        #         method=method,
        #         params=params
        #     )

    async def _recursive_data_extractor(
            self,
            url: str,
            session: aiohttp.ClientSession,
            base_params: dict = None,
            *,
            league: str,
            mapped_name: dict,
            date_restriction: bool = False,
            date_limit: int = 7,
    ) -> list[dict]:
        data = []

        async def looper(params):
            api_data = await self.call_with_retry(
                session=session,
                url=self.book_data.url.get(url),
                method=self.book_data.method,
                params=params,
            )

            if not api_data or not api_data.get("success"):
                return

            for event, market in self._iter_active_markets(api_data.get("events", [])):
                if not self._valid_market(market, date_restriction, date_limit):
                    continue

                data.append({
                    "event": event.get("title"),
                    "ticker": market.get("ticker"),
                    "yes_sub_title": market.get("yes_sub_title"),
                    "run_opposite": True if mapped_name.get("kalshi_market_name") != "Moneyline" else False,
                    "kalshi_market_name": mapped_name.get("kalshi_market_name"),
                    "common": {
                        "date": self.game_date_from_event_ticker(market.get("ticker")),
                        "league": league,
                        "line": market.get("floor_strike", None),
                        "market": mapped_name.get("actual_name", mapped_name.get("kalshi_market_name")),
                        "player": None
                    },
                })

            if cursor := api_data.get("cursor"):
                await looper({**params, "cursor": cursor})

        await looper(base_params or {})
        return data

    def _iter_active_markets(self, events):
        """Generator to iterate through events and their markets."""
        for event in events:
            for market in event.get("markets", []):
                yield event, market

    def _valid_market(self, market, date_restriction, date_limit):
        """Check if the market is active and within the date range if required."""
        if market.get("status") != "active":
            return False

        close_time = market.get("expected_expiration_time")
        if date_restriction and (
                not close_time
                or not self.within_date_range(date_limit, close_time)
        ):
            return False

        return True

    def game_date_from_event_ticker(self, event_ticker: str) -> str | None:
        """Extracts the game date from the event ticker in 'YYMMMDD' format and returns it as 'YYYY-MM-DD'."""
        match = re.search(r"-(\d{2}[A-Z]{3}\d{2})", event_ticker)
        if not match:
            return None

        date_obj = datetime.strptime(match.group(1), "%y%b%d").date()
        return date_obj.strftime("%Y-%m-%d")


    def price_to_american(self, price: float) -> int | None:
        """
        Convert price to american odds, factoring in the fees.
        We calculate the odds based on fee's so that the odds don't seem better then they are.
        """
        if price <= 0 or price >= 1:
            return None

        # Calculate Kalshi fee structure
        fee = 0.07 * price * (1.0 - price)

        # Total Risk
        risk = price + fee

        # Profit is what you keep after fees and price paid.
        net_profit = 1.0 - price - fee

        # Convert to American
        if price >= 0.5:
            # Favorites Side - Returns American Odds factoring in risk/profit
            return int(round(-100 * (risk / net_profit)))
        else:
            # Underdogs Side - Returns American Odds factoring in risk/profit
            return int(round(100 * (net_profit / risk)))

    async def _extract_order_book_data(self, session, ticker, run_opposite, extra_data=None) -> dict[str, Game] | None:
        api_data = await self.call_with_retry(
            session=session,
            url=self.book_data.url.get("orders").format(ticker=ticker),
            method=self.book_data.method,
            params={}
        )


        if api_data and api_data.get("orderbook", {}):
            liquidity_list = {}

            handler_cls = make_handler(market_name=extra_data.get("kalshi_market_name"), event_data=extra_data)
            formatted_data = handler_cls.format_data()

            key = formatted_data["key"]

            bucket = liquidity_list.setdefault(
                key,
                Game(
                    key=key,
                    event=formatted_data.get("event"),
                    start_date=formatted_data["date"],
                    league=LEAGUES.get(formatted_data.get("league").lower(), formatted_data.get("league").upper()),
                    team_1=formatted_data.get("team_1").lower(),
                    team_2=formatted_data.get("team_2").lower(),
                    orders=[]
                )
            )


            orders = api_data.get("orderbook", {})

            ####
            # Since Kalshi only shows bids in orderbook endpoint, we must convert the bids to asks.
            # For example, if we are looking at Washington Moneyline, we must look at the "NO" bids to find the "YES" asks.
            ####

            no_bids = orders.get("no", [])
            if no_bids:
                # Reversed, so we get the best price, 1st.
                for bid_price_cents, contracts in reversed(no_bids):
                    # We take 1 - that bid price to get the 'Yes' price and / 100.0 to convert to dollars.
                    # Example, if they bid 76 cents for 'No', the cost for 'Yes' is the remaining 24 cents.
                    # Used to calculate the price to buy the 'Yes' side.
                    yes_price = (100 - bid_price_cents) / 100.0

                    # We take the bid price of 'No' to determine how much money they put up to back their side.
                    # We then multiply by the number of contracts to get total liquidity.
                    # Used to calculate the total liquidity available to buy the 'Yes' side.
                    total_liq = (bid_price_cents / 100.0) * float(contracts)

                    order = Order(
                        price=yes_price,
                        liquidity=round(total_liq, 2),
                        american_odds=self.price_to_american(yes_price),
                        is_best=(bid_price_cents == no_bids[-1][0]),
                        line=formatted_data.get("line"),
                        market=STAT_TYPES.get(formatted_data.get("market").lower(), formatted_data.get("market")),
                        player=formatted_data.get("player"),
                        bet_info=formatted_data.get("bet_info").lower() if formatted_data.get("bet_info") else None,
                        player_team=formatted_data.get("player_team").lower() if formatted_data.get("player_team") else None,
                    )

                    bucket.orders.append(order)

            yes_bids = orders.get("yes", [])

            if run_opposite and yes_bids:
                extra_data["opposite"] = True
                formatted_data = handler_cls.format_data(opposite=True)

                for bid_price_cents, contracts in reversed(yes_bids):
                    no_price = (100 - bid_price_cents) / 100.0

                    total_liq = (bid_price_cents / 100.0) * float(contracts)

                    order = Order(
                        price=no_price,
                        liquidity=round(total_liq, 2),
                        american_odds=self.price_to_american(no_price),
                        is_best=(bid_price_cents == yes_bids[-1][0]),
                        line=formatted_data.get("line"),
                        market=formatted_data.get("market"),
                        player=formatted_data.get("player"),
                        bet_info=formatted_data.get("bet_info"),
                        player_team=formatted_data.get("player_team"),
                    )

                    bucket.orders.append(order)

            return liquidity_list

    async def _run_league_tasks(self, league: str, raw_market: str, mapped_name: dict, session: aiohttp.ClientSession, sem: asyncio.Semaphore = 5) -> list[dict]:
        """Helper function to run league tasks with semaphore control."""
        series_ticker = raw_market.replace("_", league.upper())
        base_params = {
            "limit": 200,
            "series_ticker": series_ticker,
            "with_nested_markets": "true",
        }

        async with sem:
            return await self._recursive_data_extractor(
                url="events",
                session=session,
                base_params=base_params,
                league=league,
                mapped_name=mapped_name,
            )

    async def _fetch_orders(self, event: dict, session: aiohttp.ClientSession, sem: asyncio.Semaphore = 5) -> dict[str, Game] | None:
        """Helper function to fetch orders with semaphore control."""
        async with sem:
            return await self._extract_order_book_data(
                session,
                event.get("ticker"),
                event.get("run_opposite"),
                extra_data=event,
            )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            if not self.proxy_list:
                raise ValueError("No proxies available for Kalshi API calls.")

            sem_length = len(self.proxy_list) * 4
            sem = asyncio.Semaphore(sem_length)

            tasks = [
                self._run_league_tasks(
                    league=league,
                    raw_market=raw_market,
                    mapped_name=self.MAPPER.get(raw_market, raw_market),
                    session=session,
                    sem=sem
                )
                for sport_info in Kalshi.SPORTS.values()
                for league in sport_info["leagues"]
                for raw_market in sport_info["markets"]
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            event_results = [
                event
                for res in results
                if isinstance(res, list)
                for event in res
            ]

            tasks = [
                self._fetch_orders(
                    event=event,
                    session=session,
                    sem=sem
                )
                for event in event_results
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            game_data = {}

            for result in results:
                if isinstance(result, dict):
                    for key, value in result.items():
                        if key in game_data:
                            game_data[key].orders.extend(value.orders)
                        else:
                            game_data[key] = value

            kalshi_data = list(game_data.values())
            return await self._database_mapper(sportsbook_data=kalshi_data)

if __name__ == "__main__":
    kalshi = Kalshi()
    asyncio.run(kalshi.run_book())