import asyncio
from dataclasses import asdict
import aiohttp

from Cross_Market.BettorOdds.bettorodds_odds import BettorOdds
from Cross_Market.Novig.novig_models import LiquidityData, GameDetails, Player, Orders
from Cross_Market.Novig.novig_api_helper import NovigAPI
from Cross_Market.Novig.novig_mapping import STAT_MAPPER

class Novig:
    def __init__(self):
        self._novig_api = NovigAPI()
        self.leagues = [
            "NFL", "NCAAF", "MLB", "NHL", "SOCCER", "PGA", "ATP", "WTA", "NBA", "UFC", "NCAAWB"
        ]

    def get_league_ids(self, league_info):
        """Get all the league IDs for a given league that are scheduled within the next 24 hours."""
        return [
            league_id
            for league in (league_info.get("data", {}).get("event", []))
            if (league_id := league.get("id"))
        ]


    async def fetch_data(self, session):
        """Fetch data for a specific league and filter it based on the league's events."""
        raw_leagues = await self._novig_api.query_caller(session, "all_leagues", no_params=True)
        leagues = self._extract_leagues(raw_leagues)
        league_results = await asyncio.gather(
            *[self._novig_api.query_caller(session, "league", league=league) for league in leagues]
        )

        league_ids = [self.get_league_ids(result) for result in league_results]
        combined = dict(zip(leagues, league_ids))

        tasks = [
            self.fetch_and_filter(session, event_id, league_name)
            for league_name, event_ids in combined.items()
            for event_id in event_ids
        ]

        results = await asyncio.gather(*tasks)
        flat_results = [market for sublist in results for market in sublist]
        return flat_results

    async def fetch_and_filter(self, session, event_id, league):
        """Fetch market data for a specific event and filter it based on the league."""
        market_data = await self._novig_api.query_caller(session, "market", event_id=event_id)
        market_data = self._extract_data(market_data, league)

        return market_data

    @staticmethod
    def price_to_american(price: float) -> int:
        if price >= 1 or price <= 0:
            raise ValueError("Price must be between 0 and 1 (exclusive).")

        if price >= 0.5:
            odds = - (price / (1 - price)) * 100
        else:
            odds = ((1 - price) / price) * 100

        return int(round(odds))

    @staticmethod
    def calculate_liquidity(qty, price):
        return (1-price) * (qty / 100)

    def _get_highest_order(self, orders, direction_description, link_id, stat_type):
        if not orders:
            return None

        highest = max(orders, key=lambda o: o["qty"] * o["price"])
        total_liquidity = sum(self.calculate_liquidity(order.get("qty"), order.get("price")) for order in orders)
        total_qty = sum(order.get("qty", 0) for order in orders)
        weighted_avg_price = sum(
            order.get("price", 0) * order.get("qty", 0) for order in orders
        ) / total_qty

        if stat_type == "Moneyline" or stat_type == "Spread":
            side = direction_description
        else:
            side = "over" if "over" in direction_description.lower() else "under"

        return {
            "total_win": round(highest["qty"] / 100, 2),
            "total_risk": round(highest["price"] * (highest["qty"] / 100), 2),
            "liquidity_left": round(self.calculate_liquidity(highest["qty"], highest["price"]), 2),
            "american_price": self.price_to_american(highest["price"]),
            "total_liquidity": round(total_liquidity, 2),
            "cost_avg_odds": round(self.price_to_american(weighted_avg_price), 2),
            "side": side,
            "outcome_id": link_id,
            "mobile_link": f"https://novig.onelink.me/JHQQ/events/{link_id}",
            "desktop_link": f"https://app.novig.us/events/{link_id}"
        }

    def _extract_data(self, market_data, league):
        import json
        with open("raw_market.json", "w") as f:
            json.dump(market_data, f, indent=4)

        market_data_list = []

        for event in market_data.get("data").get("event", []):
            for market in event.get("markets", []):
                if len(market.get("outcomes", [])) <= 0:
                    continue

                key_market_description = market.get("description", "")
                market_name = STAT_MAPPER.get(market.get("type").lower(), market.get("type"))
                bettor_odds_key = f'{event.get("description").replace(" ", "_")}_{event.get("game", {}).get("scheduled_start")}_{market_name}'

                market_data_list.extend([
                    Player(
                        player_name=market.get("player", {}).get("full_name") if market.get("player") else None,
                        stat_type=market_name,
                        league=league,
                        bet_info=outcome.get("description").title() if outcome.get("description") else None,
                        line=market.get("strike") if market.get("strike") != 0 else None,
                        key_name=key_market_description,
                        orders=[
                            Orders(
                                outcome_id=outcome.get("id"),
                                qty=order.get("qty"),
                                decimal_price=order.get("price"),
                                original_qty=order.get("originalQty"),
                                created_at=order.get("created_at"),
                                american_price=self.price_to_american(order.get("price")),
                                total_win=round(order.get("qty") / 100,2),
                                total_risk=round(order.get("price") * (order.get("qty") / 100), 2),
                                liquidity_left=round(self.calculate_liquidity(order.get("qty"), order.get("price")), 2)
                            )

                            for order in outcome.get("orders", [])
                            if order.get("status") == "OPEN"
                        ],
                        liquidity_data=LiquidityData(
                            highest_order=self._get_highest_order(outcome.get("orders", []), outcome.get("description"), outcome.get("id"), market_name)
                        ),
                        game_details=GameDetails(
                            game_title=event.get("description"),
                            game_start_time=event.get("game", {}).get("scheduled_start"),
                            bettor_odds_key=outcome.get("id")
                        )
                    )
                    for outcome in market.get("outcomes", [])
                    if any(order.get("status") == "OPEN" for order in outcome.get("orders", []))
                ])
        return market_data_list

    def _extract_leagues(self, raw_league_data):
        return [
            league.get("league")
            for league in raw_league_data.get("data", {}).get("game")
        ]


    async def run(self):
        async with aiohttp.ClientSession() as session:
            results = await self.fetch_data(session)

            bettorodds = BettorOdds()
            bettorodds_data = bettorodds.run_bettorodds()

            for game in results:
                bettorodds_key = game.game_details.bettor_odds_key
                if bettorodds_data.get(bettorodds_key):
                    bettorodds_data[bettorodds_key].update({
                        "novig_orders": [asdict(order) for order in game.orders],
                        "liquidity_info":  asdict(game.liquidity_data)
                    })

            return list(bettorodds_data.values())

    @classmethod
    async def get_raw_data(cls, leagues: list):
        """Fetch raw market data for all leagues without filtering, grouped by league."""
        api = NovigAPI()

        async with aiohttp.ClientSession() as session:
            # Fetch league-level data
            league_responses = await asyncio.gather(
                *(api.query_caller(session, "league", league=league) for league in leagues)
            )

            league_data = {league: resp for league, resp in zip(leagues, league_responses)}

            # For each league, fetch markets for all event IDs
            results = {}
            for league, resp in league_data.items():
                event_ids = [
                    event.get("id")
                    for event in resp.get("data", {}).get("event", [])
                    if event.get("id")
                ]

                if not event_ids:
                    results[league] = []
                    continue

                market_responses = await asyncio.gather(
                    *(api.query_caller(session, "market", event_id) for event_id in event_ids)
                )
                results[league] = market_responses

            return results


#
if __name__ == "__main__":
    # Create Novig instance
    novig = Novig()

    # Run it
    results = asyncio.run(novig.run())

    import json
    with open("filtered.json", "w") as f:
        # json.dump([asdict(player) for player in results], f, indent=4)
        json.dump(results, f, indent=2)



# if __name__ == "__main__":
#     raw = asyncio.run(Novig.get_raw_data(["NFL"]))
#     import json
#     with open("raw.json", "w") as f:
#         json.dump(raw, f, indent=4)