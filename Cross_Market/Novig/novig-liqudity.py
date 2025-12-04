import asyncio

from novig import Novig

class NovigLiqudity:
    LEAGUES = [
         "NFL"
    ]

    @staticmethod
    def calculate_liquidity(qty, price):
        return (1-price) * (qty / 100)

    @staticmethod
    def price_to_american(price: float) -> int:
        if price >= 1 or price <= 0:
            raise ValueError("Price must be between 0 and 1 (exclusive).")

        if price >= 0.5:
            odds = - (price / (1 - price)) * 100
        else:
            odds = ((1 - price) / price) * 100

        return int(round(odds))

    async def get_raw_data(self):
        raw = await Novig.get_raw_data(self.LEAGUES)
        return self.format_data(raw)

    def format_data(self, raw_data: dict):
        formatted_data = []

        for league, league_info in raw_data.items():
            for league_data in league_info:
                for event in league_data.get("data", {}).get("event"):
                    game_data = {
                        "event": event.get("description"),
                        "start_date": event.get("game", {}).get("scheduled_start"),
                    }

                    for market in event.get("markets", []):
                        market_type = market.get("type")
                        additional_description = market.get("description")
                        line = market.get("strike")
                        player = market.get("player", {}).get("full_name") if market.get("player") else None

                        for outcome in market.get("outcomes", []):
                            description = outcome.get("description")
                            orders = [
                                {
                                    "status": order.get("status"),
                                    "american_odds": float(self.price_to_american(order.get("price"))),
                                    "liquidity_amount": round(self.calculate_liquidity(order.get("qty"), order.get("price")),2),
                                    "created_at": order.get("created_at"),
                                }
                                for order in outcome.get("orders", [])
                                if order
                            ]

                            total_liquidity = sum(order["liquidity_amount"] for order in orders)


                            formatted_data.append({
                                "league": league,
                                "event": game_data["event"],
                                "start_date": game_data["start_date"],
                                "market_type": market_type,
                                "additional_description": additional_description,
                                "line": line,
                                "total_liquidity": round(total_liquidity,2),
                                "player": player,
                                "outcome": description,
                                "orders": orders,
                            })
        return formatted_data



if __name__ == "__main__":
    data = asyncio.run(NovigLiqudity().get_raw_data())
    import json

    with open("novig_liquidity_output_final.json", "w") as f:
        json.dump(data, f, indent=4)



#
#
#
# if __name__ == "__main__":
#     asyncio.run(NovigLiqudity().get_raw_data())

#     raw = asyncio.run(Novig.get_raw_data(["NFL", "NHL"]))
#
#     import json
#     with open("novig_output.json", "w") as f:
#         json.dump(raw, f, indent=4)