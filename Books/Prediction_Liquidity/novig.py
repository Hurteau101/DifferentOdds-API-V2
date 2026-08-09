import asyncio
from datetime import datetime, timedelta
import re
from collections import defaultdict
from itertools import chain
from typing import Iterable

from Books.Prediction_Liquidity.Helper.novig_api_helper import NovigApiHelper
from Settings.Models.base_models import GameData, TeamData, OddsFormat
import aiohttp
from Settings.Models.prediction_liquidity_models import PredictionLiquidityStats, LiquidityData
from Books.Bases.prediction_liquidity_base import PredictionLiquidityBase
from curl_cffi import AsyncSession as CurlAsyncSession


class Novig(PredictionLiquidityBase):
    def __init__(self):
        super().__init__(book_name="novig")

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
        return (1 - price) * (qty / 100)

    async def get_leagues(self, session: CurlAsyncSession, include_leagues_without_liquidity: bool = False,
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

        if not api_league_data:
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


    # def organize_orders(self, order_list: list, outcome_id: str):
    #     open_orders = [o for o in order_list if o.get("status") == "OPEN"]
    #
    #     best_price = max(
    #         (order["price"] for order in open_orders if order.get("price") is not None),
    #         default=None
    #     )
    #
    #     return [
    #         {
    #             "outcome_id": outcome_id,
    #             "qty": order.get("qty"),
    #             "decimal_price": order.get("price"),
    #             "original_qty": order.get("originalQty"),
    #             "created_at": order.get("created_at"),
    #             "price": order.get("price"),
    #             "american_price": self.price_to_american(order.get("price")),
    #             "total_win": round(order.get("qty") / 100, 2),
    #             "total_risk": round(order.get("price") * (order.get("qty") / 100), 2),
    #             "liquidity_left": round(self.calculate_liquidity(order.get("qty"), order.get("price"))),
    #             "is_best": order.get("price") == best_price
    #         }
    #         for order in open_orders
    #     ]

    def organize_orders(self, order_list: list, outcome_id: str):
        open_orders = [o for o in order_list if o.get("status") == "OPEN"]

        best_price = min(
            (order["price"] for order in open_orders if order.get("price") is not None),
            default=None
        )

        return [
            LiquidityData(
                odds_format=OddsFormat(
                    american_odds=self.price_to_american(order.get("price")),
                    decimal_odds=order.get("price"),
                ),
                liquidity=round(self.calculate_liquidity(order.get("qty"), order.get("price"))),
                price=order.get("price"),
                is_best=order.get("price") == best_price,
                additional_information={
                    "outcome_id": outcome_id,
                    "qty": order.get("qty"),
                    "original_qty": order.get("originalQty"),
                    "created_at": order.get("created_at"),
                    "total_win": round(order.get("qty") / 100, 2),
                    "total_risk": round(order.get("price") * (order.get("qty") / 100), 2),
                    "market_id": order.get("market_id"),
                }
            )
            for order in sorted(open_orders, key=lambda o: o.get("price") or 0, reverse=False)
        ]

    # async def _filter_data(self, event_data: list, league_name: str):
    #
    #     merged = {}
    #
    #     for raw_event in event_data:
    #         event_name = raw_event.get("description", "")
    #         teams = re.split(r'\s*(?:vs|@)\s*', event_name)
    #         event_obj = {
    #             "event_name": event_name,
    #             "league": league_name,
    #             "start_date": raw_event.get("game", {}).get("scheduled_start"),
    #             "team_data": {
    #                 "team_a": teams[0] if len(teams) > 1 else None,
    #                 "team_b": teams[1] if len(teams) > 1 else None,
    #                 "team_a_abbreviation": None,
    #                 "team_b_abbreviation": None
    #             },
    #             "odds": []
    #         }
    #
    #         for market in raw_event.get("markets", []):
    #             outcomes = market.get("outcomes", [])
    #             if not outcomes:
    #                 continue
    #
    #             market_name = market.get("type", "")
    #             player = market.get("player", {}).get("full_name") if market.get("player") else None
    #             line = market.get("strike") if market.get("strike") != 0 else None
    #
    #             for outcome in outcomes:
    #                 orders = self.organize_orders(outcome.get("orders", []), outcome.get("id"))
    #                 if not orders:
    #                     continue
    #
    #                 bet_info = outcome.get("description")
    #
    #                 modified_info = (
    #                     bet_info
    #                     if not any(t.lower() in ["over", "under"] for t in bet_info.split())
    #                     else bet_info.replace(str(line), "").strip()
    #                 )
    #
    #                 if modified_info not in ["Over", "Under"]:
    #                     cleaned_name = re.sub(r"\s[+-].*$", "", modified_info).lower()
    #                     bet_team = teams[0] if (cleaned_name == teams[0].lower() or cleaned_name in teams[0].lower()) else teams[1]
    #
    #                 else:
    #                     bet_team = None
    #
    #
    #                 event_obj["odds"].append(
    #                     {
    #                         "market": market_name,
    #                         "line": line,
    #                         "player": player,
    #                         "bet_team": bet_team,
    #                         "bet_type": modified_info if modified_info in ["Over", "Under"] else None,
    #                         "orders": orders
    #                     }
    #                 )
    #
    #         if event_obj["odds"]:
    #             merged[raw_event.get("id")] = event_obj
    #
    #
    #     return list(merged.values())

    async def _filter_data(self, event_data: list, league_name: str):

        merged = {}

        for raw_event in event_data:
            start_date = raw_event.get("game", {}).get("scheduled_start")
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            new_dt = dt - timedelta(minutes=5)
            start_date_minus_5 = new_dt.isoformat().replace("+00:00", "Z")


            event_name = raw_event.get("description", "")
            teams = re.split(r'\s*(?:vs|@)\s*', event_name)
            event_obj = GameData(
                league=league_name,
                start_date=start_date_minus_5,
                game_key=event_name,
                team_data=TeamData(team_a=teams[0], team_b=teams[1]),
                odds=[],
            )

            for market in raw_event.get("markets", []):
                outcomes = market.get("outcomes", [])
                if not outcomes:
                    continue

                market_name = market.get("type", "").replace("_", " ")

                player = market.get("player", {}).get("full_name") if market.get("player") else None
                line = market.get("strike") if market.get("strike") != 0 else None

                for outcome in outcomes:
                    orders = self.organize_orders(outcome.get("orders", []), outcome.get("id"))
                    if not orders:
                        continue

                    bet_info = outcome.get("description").lower()

                    modified_info = (
                        bet_info.lower()
                        if not any(t.lower() in ["over", "under"] for t in bet_info.split())
                        else bet_info.replace(str(line), "").strip()
                    )

                    if modified_info not in ["over", "under"]:
                        cleaned_name = re.sub(r"\s[+-].*$", "", modified_info).lower()
                        bet_team = teams[0] if (cleaned_name == teams[0].lower() or cleaned_name in teams[0].lower()) else teams[1]

                    else:
                        bet_team = None

                    stats = PredictionLiquidityStats(
                            line=line,
                            bet_type=modified_info if modified_info in ["over", "under"] else None,
                            market=market_name,
                            liquidity_data=orders,
                            bet_player=player,
                            bet_team=bet_team,
                            player_team=None,
                            future=False,
                    )

                    stats.market = self.special_stat_mapper(stats.market, league_name)
                    event_obj.odds.append(stats)

                    # event_obj.odds.append(
                    #     PredictionLiquidityStats(
                    #         line=line,
                    #         bet_type=modified_info if modified_info in ["over", "under"] else None,
                    #         market=market_name,
                    #         liquidity_data=orders,
                    #         bet_player=player,
                    #         bet_team=bet_team,
                    #         player_team=None,
                    #         future=False,
                    #     )
                    # )

            if event_obj.odds:
                merged[raw_event.get("id")] = event_obj


        return list(merged.values())


    async def _fetch_and_filter_markets(self, session: CurlAsyncSession, novig_api_helper: NovigApiHelper,
                                        event_id: str, league_name: str) -> Iterable[GameData] | None:
        """
        Fetches and filters market data from Novig API.
        :param session: aiohttp ClientSession for making requests.
        :param novig_api_helper: NovigApiHelper instance.
        :param event_id: ID of the event.
        :param league_name: Name of the league.
        """
        markets = await self.api_caller(
            session=session,
            url=self.book_data.url.get("base_url"),
            json=novig_api_helper.query_caller(
                query_parameter="market",
                event_id=event_id
            ),
            method=self.book_data.method,
            headers=self.book_data.headers
        )


        if not markets:
            return None

        event_data = markets.get("data", {}).get("event", [])
        return await self._filter_data(event_data, league_name=league_name)

    # async def convert_to_dataclass(self, event_data):
    #     games = []
    #
    #     for event in event_data:
    #         odds_list = []
    #
    #         for selection_name, market in event.get("markets", {}).items():
    #             liquidity_entries = [
    #                 {
    #                     "odds_format": OddsFormat(
    #                         american_odds=odd["odds_format"].get("american_odds"),
    #                         decimal_odds=odd["odds_format"].get("decimal_odds"),
    #                     ),
    #                     "liquidity": odd.get("liquidity"),
    #                     "price": odd.get("price"),
    #                     "is_best": odd.get("is_best"),
    #                 }
    #                 for odd in market.get("odds", [])
    #             ]
    #
    #             stat = PredictionLiquidityStats(
    #                 line=market.get("line"),
    #                 bet_type=market.get("bet_type"),
    #                 future=False,
    #                 live=False,
    #                 market=market.get("market"),
    #                 liquidity_data=liquidity_entries,
    #                 bet_player=None,
    #                 bet_team=None,
    #                 player_team=None,
    #             )
    #
    #             odds_list.append(stat)
    #
    #         game = GameData(
    #             league=event.get("league"),
    #             start_date=event.get("start_date"),
    #             game_key=event.get("game_key"),
    #             team_data=TeamData(**event.get("team_data")),
    #             odds=odds_list,
    #             solo_game=False,
    #         )
    #
    #         games.append(game)
    #
    #     return games


    async def run_book(self):
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            leagues = await self.get_leagues(session=session,
                                             excluded_leagues=["ENTERTAINMENT", "HOT", "CUSTOM", "LIVE"])

            if not leagues:
                return None

            novig_api_helper = NovigApiHelper()

            raw_league_data = await asyncio.gather(
                *(
                    self.api_caller(
                        session=session,
                        url=self.book_data.url.get("base_url"),
                        json=novig_api_helper.query_caller(
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

            game_data = list(chain.from_iterable(filter(None, market_data)))
            leagues = set()
            stat_types = set()

            mapped_data = await self.map_runner(session=session, sportsbook_data=game_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name,
            )

            await self.market_chunk_processor(mapped_data=mapped_data, book_name=self.book_data.name)

            return mapped_data

if __name__ == "__main__":
    book = Novig()
    asyncio.run(book.run_book())