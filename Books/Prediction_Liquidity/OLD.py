import asyncio
import re
from collections import defaultdict
from itertools import chain
from typing import Iterable

from Books.Prediction_Liquidity.Helper.novig_api_helper import NovigApiHelper
from Monitoring.monitoring import create_sentry_message
from Settings.Models.base_models import GameData, TeamData, OddsFormat
import aiohttp
from Settings.Models.prediction_liquidity_models import PredictionLiquidityStats
from Books.Bases.prediction_liquidity_base import PredictionLiquidityBase
from Utils.request_caller import SportbookRequestType


class Novig(PredictionLiquidityBase):
    def __init__(self):
        super().__init__(book_name="novig", request_type=SportbookRequestType.ASYNC)

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
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("league_url"),
            params={
                "displayUnseededMarkets": str(include_leagues_without_liquidity)
            },
            method="GET",
            headers=self.book_data.headers
        )

        if not api_league_data:
            create_sentry_message(
                tag_key="novig",
                tag_value="league_failure",
                message="No leagues found",
                level="error"
            )

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

    def mark_best_prices(self, events):
        for event in events:
            for market in event["markets"].values():
                odds_list = market["odds"]
                if not odds_list:
                    continue

                best_value = max(
                    o["odds_format"]["american_odds"]
                    for o in odds_list
                )

                for odd in odds_list:
                    odd["is_best"] = (
                            odd["odds_format"]["american_odds"] == best_value
                    )


    async def _group_data(self, market_data: list):
        merged = {}

        for data in market_data:
            orders = data.get("orders", [])
            if not orders:
                continue

            event_key = data.get("event_name")

            teams = re.split(r'\s*(?:vs|@)\s*', data.get("event_name"))

            event = merged.setdefault(event_key, {
                "event_name": event_key,
                "league": data.get("league"),
                "start_date": data.get("event_date"),
                "game_key": event_key,
                "team_data": {
                    "team_a": teams[0] if len(teams) > 1 else None,
                    "team_b": teams[1] if len(teams) > 1 else None,
                    "team_a_abbreviation": None,
                    "team_b_abbreviation": None
                },
                "markets": {}
            })

            line = data.get("line")
            bet_info = data.get("bet_info") or ""

            modified_info = (
                bet_info
                if not any(t.lower() in ["over", "under"] for t in bet_info.split())
                else bet_info.replace(str(line), "").strip()
            )

            market_details = event["markets"].setdefault(
                bet_info,
                {
                    "market": data.get("stat_type"),
                    "line": line,
                    "bet_type": modified_info,
                    "odds": []
                }
            )

            stat_bucket = market_details["odds"]

            for order in orders:
                stat_bucket.append({
                    "odds_format": {
                        "american_odds": order.get("american_price"),
                        "decimal_odds": order.get("decimal_price"),
                    },
                    "price": order.get("price"),
                    "liquidity": order.get("liquidity_left"),
                })

            # market_details = event["markets"].setdefault(
            #     bet_info,
            #     {
            #         "market": data.get("stat_type"),
            #         "line": line,
            #         "bet_type": modified_info,
            #         "odds": {}
            #     }
            # )
            #
            # # stat_bucket = event["odds"].setdefault(bet_info, [])
            # stat_bucket = market_details["odds"].setdefault(bet_info, [])
            #
            # for order in orders:
            #     stat_bucket.append({
            #         # "market": data.get("stat_type"),
            #         # "line": line,
            #         # "bet_type": modified_info,
            #         # "odds": [
            #         #     {
            #         #         "Test": 1
            #         #     }
            #         # ]
            #
            #         "odds_format": {
            #             "american_odds": order.get("american_price"),
            #             "decimal_odds": order.get("decimal_price"),
            #         },
            #         # "liquidity": order.get("liquidity_left"),
            #         # "line": line,
            #         # "bet_type": modified_info,
            #         # "market": data.get("stat_type"),
            #     })

        return list(merged.values())

    # async def _group_data(self, market_data: list):
    #     merged = {}
    #
    #     for data in market_data:
    #         if len(data.get("orders")) == 0:
    #             continue
    #
    #         event_key = data.get("event_name")
    #
    #         event = merged.setdefault(event_key, {
    #             "event_name": event_key,
    #             "league": data.get("league"),
    #             "start_date": data.get("event_date"),
    #             "game_key": event_key,  # replace if you have a real key
    #             "team_data": {
    #                 "team_a": None,
    #                 "team_b": None,
    #                 "team_a_abbreviation": None,
    #                 "team_b_abbreviation": None
    #             },
    #             "odds": []
    #         })
    #
    #         line = data.get("line")
    #         bet_info = data.get("bet_info")
    #         modified_info = bet_info if not any(
    #             text.lower() in ["over", "under"]
    #             for text in bet_info.split(" ")
    #         ) else bet_info.replace(str(line), "").strip()
    #
    #         stat_bucket = event["odds"].setdefault(modified_info, [])
    #
    #         for order in data.get("orders", []):
    #             stat_bucket.append({
    #                 **order,
    #                 "line": line,
    #                 "bet_type": modified_info,
    #                 "market": data.get("stat_type"),
    #             })
    #
    #
    #             # event["odds"].append({
    #             #     "line": data.get("line"),
    #             #     "bet_type": modified_info,
                #     "odds_format": {
                #         "american_odds": order.get("american_price")
                #     },
    #             #     "market": data.get("stat_type"),
    #             #     "liquidity": order.get("liquidity_left"),
    #             #     "is_best": False,
    #             #     "bet_team": data.get("bet_info") if "-" in data.get("bet_info") else None,
    #             #     "player_team": None,
    #             #     "price": order.get("price"),
    #             # })
    #
    #     return list(merged.values())

    # async def _group_data(self, market_data: list):
    #     """
    #     Organize the data into groups based on the bet_info.
    #     :param market_data: List of market data.
    #     """
    #     # grouped_data = defaultdict(
    #     #     lambda: GameData(
    #     #         game_key=None,
    #     #         league=None,
    #     #         start_date=None,
    #     #         team_data=None,
    #     #         odds={},
    #     #     )
    #     # )
    #
    #     merged = {}
    #
    #     for data in market_data:
    #         key = data.get("event_name")
    #
    #         market = merged.setdefault(key, {
    #             "league": data.get("league"),
    #             "player_name": data.get("player_name"),
    #             "event_name": data.get("event_name"),
    #             "event_date": data.get("event_date"),
    #             "key_name": key,
    #             "orders": []
    #         })
    #
    #         # market["orders"].extend(data.get("orders", []))
    #         for order in data.get("orders", []):
    #             market["orders"].append({
    #                 **order,
    #                 "stat_type": data.get("stat_type"),
    #                 "bet_info": data.get("bet_info"),
    #                 "line": data.get("line"),
    #             })
    #
    #     return list(merged.values())




        # for event in market_data:
        #     if len(event.get("orders")) == 0:
        #         continue
        #
        #     key_name = event.get("key_name")
        #     line = event.get("line")
        #
        #
        #     bet_info = event.get("bet_info")
        #     modified_info = bet_info if not any(
        #         text.lower() in ["over", "under"]
        #         for text in bet_info.split(" ")
        #     ) else bet_info.replace(str(line), "").strip()
        #
        #     game = grouped_data[key_name]
        #
        #     game.league = event.get("league")
        #     game.event = event.get("event_name")
        #     game.start_date = event.get("event_date")
        #     game.market_type = event.get("stat_type")
        #     game.line = event.get("line")
        #     game.player = event.get("player_name")
        #
        #     orders = [PredictionLiquidityStats(**order) for order in event.get("orders", [])]
        #     print(orders)
        #
        #     total_liq = sum(self.calculate_liquidity(order.qty, order.price) for order in orders)
        #     highest = max(orders, key=lambda order: order.qty * order.price)
        #
        #     game.odds.setdefault(modified_info, []).append(
        #         {
        #             "orders": orders,
        #             "total_liquidity": total_liq,
        #             "highest_order": highest
        #         }
        #     )
        #
        #     totals = [side.total_liquidity for sides in game.outcomes.values() for side in sides]
        #     if len(game.outcomes) == 2 and len(totals) == 2:
        #         game.liquidity_difference = abs(totals[0] - totals[1])
        #     elif len(game.outcomes) == 1 and len(totals) == 1:
        #         game.liquidity_difference = abs(totals[0])
        #
        #
        # # return grouped_data.values()

    async def _filter_data(self, event_data: list, league_name: str) -> Iterable[GameData]:
        """
        Filters through the market data and extracts necessary data to create a Game object.
        :param event_data: List of market data.
        :param league_name: Name of the league.
        """
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
                                "total_win": round(order.get("qty") / 100, 2),
                                "total_risk": round(order.get("price") * (order.get("qty") / 100), 2),
                                "liquidity_left": round(self.calculate_liquidity(order.get("qty"), order.get("price")),
                                                        2)
                            }

                            for order in outcome.get("orders", [])
                            if order.get("status") == "OPEN" and len(outcome.get("orders", [])) > 0
                        ],
                    }

                    for outcome in market.get("outcomes", [])
                ])


        return await self._group_data(market_data)

    async def _fetch_and_filter_markets(self, session: aiohttp.ClientSession, novig_api_helper: NovigApiHelper,
                                        event_id: str, league_name: str) -> Iterable[GameData] | None:
        """
        Fetches and filters market data from Novig API.
        :param session: aiohttp ClientSession for making requests.
        :param novig_api_helper: NovigApiHelper instance.
        :param event_id: ID of the event.
        :param league_name: Name of the league.
        """
        markets = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("base_url"),
            payload=novig_api_helper.query_caller(
                query_parameter="market",
                event_id=event_id
            ),
            method=self.book_data.method,
            headers=self.book_data.headers
        )

        if not markets:
            create_sentry_message(
                tag_key="novig",
                tag_value="market_failure",
                message="No markets found",
                level="error"
            )

            return None

        event_data = markets.get("data", {}).get("event", [])
        return await self._filter_data(event_data, league_name=league_name)

    async def convert_to_dataclass(self, event_data):
        games = []

        for event in event_data:
            odds_list = []

            for selection_name, market in event.get("markets", {}).items():
                liquidity_entries = [
                    {
                        "odds_format": OddsFormat(
                            american_odds=odd["odds_format"].get("american_odds"),
                            decimal_odds=odd["odds_format"].get("decimal_odds"),
                        ),
                        "liquidity": odd.get("liquidity"),
                        "price": odd.get("price"),
                        "is_best": odd.get("is_best"),
                    }
                    for odd in market.get("odds", [])
                ]

                stat = PredictionLiquidityStats(
                    line=market.get("line"),
                    bet_type=market.get("bet_type"),
                    future=False,
                    live=False,
                    market=market.get("market"),
                    liquidity_data=liquidity_entries,
                    bet_player=None,
                    bet_team=None,
                    player_team=None,
                )

                odds_list.append(stat)

            game = GameData(
                league=event.get("league"),
                start_date=event.get("start_date"),
                game_key=event.get("game_key"),
                team_data=TeamData(**event.get("team_data")),
                odds=odds_list,
                solo_game=False,
            )

            games.append(game)

        return games


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            leagues = await self.get_leagues(session=session,
                                             excluded_leagues=["ENTERTAINMENT", "HOT", "CUSTOM", "LIVE"])
            if not leagues:
                return None

            novig_api_helper = NovigApiHelper()

            raw_league_data = await asyncio.gather(
                *(
                    self.api_caller(
                        book_name=self.book_data.name,
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

            data = list(chain.from_iterable(filter(None, market_data)))
            self.mark_best_prices(data)
            new_data = await self.convert_to_dataclass(data)
            return new_data
            # print(new_data)
            #
            # with open("test2.json", "w") as f:
            #     import json
            #     json.dump(data, f, indent=2)

if __name__ == "__main__":
    book = Novig()
    asyncio.run(book.run_book())