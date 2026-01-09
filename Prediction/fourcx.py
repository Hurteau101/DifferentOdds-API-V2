import re
import aiohttp
import asyncio
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Redis.redis_manager import RedisSync
from Settings.Prediction_Settings.prediction_book_base import PredictionBookBase
from Settings.Prediction_Settings.prediction_model import Game, Order
from Settings.book_base import SportbookRequestType

# Session Expiry is 2 months typically.

class FourCX(PredictionBookBase):
    INVALID_LEAGUES = ["live", "custom", "superbowl", "nfc", "afc"] # Avoid these leagues or anything with these keywords

    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="4cx")

    async def _get_leagues(self, session: aiohttp.ClientSession) -> dict:
        leagues = await self.api_caller(
                    session=session,
                    url=self.book_data.url.get("games"),
                    headers=self.book_data.headers,
                    method=self.book_data.method,
                )

        return leagues

    @staticmethod
    def remove_ordinal(market_name: str, return_ordinal: bool = False) -> str | tuple[str, str | None] | None:
        """
        Removes ordinal indicators from market names.
        @param market_name: The market name string.
        @param return_ordinal: Whether to return the found ordinal.
        """
        if not market_name:
            return market_name

        ordinal = ["1h", "2h", "3h", "4h", "1q", "2q", "3q", "4q"]
        find_ordinal = next((oq for oq in ordinal if oq in market_name.lower()), None)
        if find_ordinal:
            modified_name = market_name.lower().replace(find_ordinal, "").replace("-", "").strip()
            return (modified_name, find_ordinal) if return_ordinal else modified_name

        return (market_name, None) if return_ordinal else market_name

    def _get_markets(self, game: dict) -> list[dict]:
        game_keys = list(game.keys())

        # All markets must contain these keys, else ignore
        required_keys = {"sumUntaken", "odds"}

        valid_markets = []

        for market_keys in game_keys:
            market_data = game.get(market_keys)
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

    def _configure_market_name(self, ordinal: str, event_name: str, order: dict, is_player_prop: bool) -> str | None:
        """
        Configures the market name. If it's a player prop, look at the event name for the player name and extract text between '()'.
        Otherwise, use the order type and map to STAT_TYPES if possible.
        @param ordinal: The ordinal indicator (e.g., "1h", "2q").
        @param event_name: The event name string.
        @param order: The order dictionary containing market details.
        @param is_player_prop: Boolean indicating if it's a player prop market.
        """
        if is_player_prop:
            name = re.findall(r"\((.*?)\)", event_name)
            return name[0] if name else None

        market_name = order.get("type", "")

        if ordinal:
            market_name = f"{ordinal} {market_name}"

        return STAT_TYPES.get(market_name.lower(), market_name.title())

    def _extract_order_details(self, game: dict) -> Game | None:
        markets = self._get_markets(game)
        if not markets:
            return None

        league, ordinal = FourCX.remove_ordinal(game.get("league"), return_ordinal=True)

        teams = {
            participant.get("id"): FourCX.remove_ordinal(participant.get("longName")) or FourCX.remove_ordinal(participant.get("shortName"))
            for index, participant in enumerate(game.get("participants", []), start=1)
        }

        if not teams:
            return None

        team_list = sorted([
            team
            for team in teams.values()
        ])

        league = LEAGUES.get(league.lower(), league.upper())
        game_date = self.cache_time(game.get("start"))

        team_keys = "_".join(team_list).replace(" ", "_")
        key = f"{league}_{team_keys}_{game_date}".lower()

        return Game(
            key=key,
            event=" vs ".join(team_list) if len(team_list) == 2 else game.get("eventName"),
            start_date=game_date,
            league=league,
            team_1=team_list[0],
            team_2=team_list[1] if len(team_list) == 2 else None,
            orders=[
                Order(
                    liquidity=order.get("sumUntaken"),
                    american_odds=order.get("odds"),
                    market=self._configure_market_name(ordinal=ordinal, event_name=game.get("eventName"), order=order, is_player_prop=True if "props" in league.lower() else False),
                    bet_team=FourCX.remove_ordinal(teams.get(order.get("participantID"))),
                    bet_type=order.get("OU"),
                    line=order.get("line"),
                    is_best=True if index == 0 else False,
                    bet_player=game.get("eventName").split("(")[0].title().strip() if "props" in league.lower() else None,
                    player_team=teams.get(order.get("participantId")) if "props" in league.lower() else None,
                )

                for index, order in enumerate(markets)
            ]
        )

    def _filter_leagues(self, league_list: list) -> list:
        """Filters out invalid leagues from the provided league list."""
        valid_leagues = []

        for league in league_list:
            league = league.lower()
            league_split = league.split("-")
            if any(invalid in league_split for invalid in self.INVALID_LEAGUES):
                continue

            valid_leagues.append(league)

        return valid_leagues


    async def run_book(self):
        redis = RedisSync(db=5)
        auth_token = redis.get("4cx_auth_token").decode("utf-8")
        if not auth_token:
            return

        async with aiohttp.ClientSession() as session:
            self.book_data.headers["Authorization"] = auth_token
            raw_leagues = await self._get_leagues(session)
            if not raw_leagues or not raw_leagues.get("data", {}).get("availableLeagues"):
                return

            leagues = raw_leagues.get("data", {}).get("availableLeagues", [])
            leagues = self._filter_leagues(leagues)

            orders = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("orders"),
                    headers=self.book_data.headers,
                    method="POST",
                    payload={"leagueRequested": league}
                )
                for league in leagues
            ]

            order_results = await asyncio.gather(*orders)

            game_data = {}

            for order in order_results:
                if not order or not order.get("success") or not order.get("data"):
                    continue

                for game in order.get("data", {}).get("games", []):
                    data = self._extract_order_details(game)
                    if data:
                        key = data.key

                        if key in game_data:
                            game_data[key].orders.extend(data.orders)
                        else:
                            game_data[key] = data


            game_list = list(game_data.values())
            return await self._database_mapper(game_list)

if __name__ == "__main__":
    four_cx = FourCX()
    asyncio.run(four_cx.run_book())


