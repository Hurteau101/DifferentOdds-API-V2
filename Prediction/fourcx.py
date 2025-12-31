import json

from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.Prediction_Settings.prediction_model import Game, Order
import aiohttp
from Redis.redis_manager import RedisSync
from Settings.Prediction_Settings.prediction_book_base import PredictionBookBase
from Settings.book_base import SportbookRequestType
import asyncio

class FourCX(PredictionBookBase):
    SPORTS = {
        "basketball": ["NBA", "NCAAB"],
        "football": ["NFL", "NCAAF"],
        "hockey": ["NHL"],
        "soccer": ["PREMIER-LEAGUE", "SERIE-A", "LA-LIGA", "BUNDESLIGA"]
    }

    def __init__(self, log_directory=None, log_name=None):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="4cx")

    ### SESSION EXPIRY IS 2 MONTHS

    def _get_market_data(self, game_data):
        game_keys = list(game_data.keys())

        # All markets must contain these keys, else ignore
        required_keys = {"sumUntaken", "odds"}

        valid_markets = []

        for market_keys in game_keys:
            market_data = game_data.get(market_keys)
            # List instances we only need to check valid keys.
            if isinstance(market_data, list):
                if all(required_keys.issubset(item.keys()) for item in market_data):
                    valid_markets.extend(market_data)
            # Dict instances we need to loop through the values:
            # Ex "awaySpreads":{"-4.5": [...], "-3.5": [...]} etc
            # So we need to get the list values from the dict and check those for valid keys.
            elif isinstance(market_data, dict):
                for line, market_values in market_data.items():
                    if isinstance(market_values, list):
                        if all(required_keys.issubset(item.keys()) for item in market_values):
                            valid_markets.extend({
                                **item,
                                "line": float(line)
                            } for item in market_values)

        return valid_markets


    def _determine_bet_info(self, market:str, line:float, team_id: str, team_data: dict, direction=None):
        if "spread" in market.lower():
            team = team_data.get(team_id)
            if team:
                return f"{line} {team.get('longName')}"
        elif "total" in market.lower():
           return f"{direction} {line}"
        elif "moneyline" in market.lower():
            team = team_data.get(team_id)
            if team:
                return f"{team.get('longName')}"

        return ""

    def _extract_orders(self, game_data: dict):
        valid_markets = self._get_market_data(game_data)
        if not valid_markets:
            return None

        # Modify if doing single sport games
        if len(game_data.get("participants", [])) != 2:
            return None

        team_data = {
            game_data.get("participants", [])[0].get("id"): game_data.get("participants", [])[0],
            game_data.get("participants", [])[1].get("id"): game_data.get("participants", [])[1]
        }

        team_1 = game_data.get("participants", [])[0]
        team_2 =  game_data.get("participants", [])[1]

        league = game_data.get("league")

        game_key = f"{league.lower()}_{team_1.get('longName').lower().replace(' ', '_')}_{team_2.get('longName').lower().replace(' ', '_')}_{game_data.get('dateGame')}"

        return Game(
            key=game_key,
            event=game_data.get("eventName").lower() if game_data.get("eventName") else None,
            start_date=self.cache_time(game_data.get("dateGame")),
            league=LEAGUES.get(game_data.get("league").lower(), game_data.get("league").upper()),
            team_1=team_1.get("longName"),
            team_1_abbreviation=team_1.get("shortName"),
            team_2=team_2.get("longName"),
            team_2_abbreviation=team_2.get("shortName"),
            orders=[
                Order(
                    liquidity=order.get("sumUntaken"),
                    american_odds=order.get("odds"),
                    market=STAT_TYPES.get(order.get("type").lower(), order.get("type").lower()),
                    line=order.get("line"),
                    bet_info=self._determine_bet_info(
                        market=order.get("type"),
                        line=order.get("line"),
                        team_id=order.get("participantID"),
                        team_data=team_data,
                        direction=order.get("OU", None)
                    ),
                )

                for order in valid_markets
            ]

        )

    async def run_book(self):
        redis = RedisSync(db=5)
        auth_token = redis.get("4cx_auth_token").decode("utf-8")
        if not auth_token:
            return

        async with aiohttp.ClientSession() as session:
            self.book_data.headers["Authorization"] = auth_token

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("games").format(league=league, sport=sport),
                    headers=self.book_data.headers,
                    method=self.book_data.method,
                )
                for sport, leagues in FourCX.SPORTS.items()
                for league in leagues
            ]

            results = await asyncio.gather(*tasks)

            game_ids = set(
                game_id.get("id")
                for result in results
                if result and result.get("success")
                for game_id in result.get("data", {}).get("games", [])
                if game_id and not game_id.get("live")
            )

            games = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("orders"),
                    headers=self.book_data.headers,
                    method="POST",
                    payload={"gameID": game_id}
                )
                for game_id in list(game_ids)
            ]


            order_results = await asyncio.gather(*games)

            game_data_dict = {}

            for order in order_results:
                if not order or not order.get("success") or not order.get("data"):
                    continue

                game_data = self._extract_orders(order.get("data", {}).get("game", {}))
                if game_data:
                    game_key = game_data.key

                    if game_key in game_data_dict:
                        game_data_dict[game_key].orders.extend(game_data.orders)
                    else:
                        game_data_dict[game_key] = game_data

            cx_data = list(game_data_dict.values())
            return await self._database_mapper(cx_data)




if __name__ == "__main__":
    four_cx = FourCX()
    asyncio.run(four_cx.run_book())