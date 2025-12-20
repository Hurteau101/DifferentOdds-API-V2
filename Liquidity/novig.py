from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from itertools import chain
import aiohttp
from Settings.Liquidity_Settings.novig_model import Game, Order, OutcomeSide
import asyncio


from Settings.Liquidity_Settings.liquidity_book_base import LiquidityBookBase
from Settings.book_base import SportbookRequestType
from Liquidity.novig_api_helper import NovigApiHelper
from Redis.redis_manager import RedisManager


class Novig(LiquidityBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="novig")

    @staticmethod
    def price_to_american(price: float) -> int:
        """Convert a decimal price to American odds."""
        if price >= 1 or price <= 0:
            raise ValueError("Price must be between 0 and 1 (exclusive).")

        if price >= 0.5:
            odds = - (price / (1 - price)) * 100
        else:
            odds = ((1 - price) / price) * 100

        return int(round(odds))

    @staticmethod
    def calculate_liquidity(qty, price):
        """Calculate the liquidity left based on quantity and price."""
        return (1-price) * (qty / 100)

    async def get_leagues(self, session: aiohttp.ClientSession, include_leagues_without_liquidity: bool = False,
                          include_sub_markets: bool = True, excluded_leagues: list = None) -> set | None:
        """
        Extract all leagues from the Novig API.
        :param session: aiohttp ClientSession for making requests.
        :param include_leagues_without_liquidity: Whether to include leagues without liquidity.
        :param include_sub_markets: Whether to include sub-markets.
        :param excluded_leagues: List of league IDs to exclude.
        :return: Set of league IDs.
        """
        api_league_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("league_url"),
            params={
                "displayUnseededMarkets": str(include_leagues_without_liquidity)
            },
            method="GET",
            headers=self.book_data.headers
        )

        if not api_league_data.get("success"):
            return None

        league_data = api_league_data.get("rankings", [])

        excluded = set(exclude.lower() for exclude in excluded_leagues) if excluded_leagues else set()

        league_set = set()

        for league in league_data:
            league_id = league.get("tabId")

            if not league_id:
                continue

            if include_sub_markets and "subLeagues" in league:
                league_set.update(
                    sub_league.get("leagueId")
                    for sub_league in league.get("subLeagues")
                    if sub_league.get("leagueId") and sub_league.get("leagueId").lower() not in excluded_leagues
                )

                # Continue as we don't want the main league ID if sub-markets are included
                continue

            if league_id and league_id.lower() not in excluded:
                league_set.add(league_id)

        return league_set

    async def _group_data(self, market_data: list):
        grouped_data = defaultdict(
            lambda: Game(
                league=None,
                event=None,
                start_date=None,
                market_type=None,
                line=None,
                player=None,
                liquidity_difference=None,
                fetched_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                outcomes={},
            )
        )


        for event in market_data:
            if len(event.get("orders")) == 0:
                continue

            key_name = event.get("key_name")
            line = event.get("line")

            bet_info = event.get("bet_info")
            modified_info = bet_info if not any(
                text.lower() in ["over", "under"]
                for text in bet_info.split(" ")
            ) else bet_info.replace(str(line), "").strip()

            game = grouped_data[key_name]

            game.league = event.get("league")
            game.event = event.get("event_name")
            game.start_date = event.get("event_date")
            game.market_type = event.get("stat_type")
            game.line = event.get("line")
            game.player = event.get("player_name")

            orders = [Order(**order) for order in event.get("orders", [])]
            total_liq = sum(self.calculate_liquidity(order.qty, order.price) for order in orders)
            highest = max(orders, key=lambda order: order.qty * order.price)

            game.outcomes.setdefault(modified_info, []).append(
                OutcomeSide(
                    orders=orders,
                    total_liquidity=total_liq,
                    highest_order=highest)
            )

            totals = [side.total_liquidity for sides in game.outcomes.values() for side in sides]
            if len(game.outcomes) == 2 and len(totals) == 2:
                game.liquidity_difference = abs(totals[0] - totals[1])
            elif len(game.outcomes) == 1 and len(totals) == 1:
                game.liquidity_difference = abs(totals[0])

        return grouped_data.values()

    async def _filter_data(self, event_data: list, league_name: str):
        market_data = []

        for event in event_data:
            for market in event.get("markets", []):
                if len(market.get("outcomes", [])) <= 0:
                    continue

                key_name = market.get("description", "")
                market_name = market.get("type", "")
                market_data.extend([
                    {
                        "league": league_name,
                        "player_name": market.get("player", {}).get("full_name") if market.get("player") else None,
                        "event_name": event.get("description"),
                        "stat_type": market_name,
                        "bet_info": outcome.get("description") if outcome.get("description") else None,
                        "line": market.get("strike") if market.get("strike") != 0 else None,
                        "event_date": event.get("game", {}).get("scheduled_start"),
                        "key_name": key_name,
                        "orders": [
                            {
                                "outcome_id": outcome.get("id"),
                                "qty": order.get("qty"),
                                "decimal_price": order.get("price"),
                                "original_qty": order.get("originalQty"),
                                "created_at": order.get("created_at"),
                                "price": order.get("price"),
                                "american_price": self.price_to_american(order.get("price")),
                                "total_win": round(order.get("qty") / 100,2),
                                "total_risk": round(order.get("price") * (order.get("qty") / 100), 2),
                                "liquidity_left": round(self.calculate_liquidity(order.get("qty"), order.get("price")), 2)
                            }

                            for order in outcome.get("orders", [])
                            if order.get("status") == "OPEN" and len(outcome.get("orders", [])) > 0
                        ],
                    }

                    for outcome in market.get("outcomes", [])
                ])


        return await self._group_data(market_data)

    async def _fetch_and_filter_markets(self, session: aiohttp.ClientSession, novig_api_helper: NovigApiHelper,
                                        event_id: str, league_name: str):
        markets = await self.api_caller(
            session=session,
            url=self.book_data.url.get("base_url"),
            payload=novig_api_helper.query_caller(
                query_parameter="market",
                event_id=event_id
            ),
            method=self.book_data.method,
            headers=self.book_data.headers
        )

        if not markets.get("success"):
            return None

        event_data = markets.get("data", {}).get("event", [])
        return await self._filter_data(event_data, league_name=league_name)


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            leagues = await self.get_leagues(session=session, excluded_leagues=["ENTERTAINMENT", "HOT", "CUSTOM", "LIVE"])
            if not leagues:
                return None

            novig_api_helper = NovigApiHelper()

            raw_league_data = await asyncio.gather(
                *(
                    self.api_caller(
                        session=session,
                        url=self.book_data.url.get("base_url"),
                        payload=novig_api_helper.query_caller(
                            query_parameter="league",
                            league=league
                        ),
                        method=self.book_data.method,
                        headers=self.book_data.headers
                    )
                    for league in leagues
                )
            )


            market_data = await asyncio.gather(
                *(
                    self._fetch_and_filter_markets(
                        session=session,
                        novig_api_helper=novig_api_helper,
                        event_id=event.get("id"),
                        league_name=league
                    )
                    for league, response_data in zip(leagues, raw_league_data)
                    for event in response_data.get("data", {}).get("event", [])
                )
            )

            return list(chain.from_iterable(filter(None, market_data)))


if __name__ == "__main__":
    import asyncio

    data = asyncio.run(Novig().run_book())

