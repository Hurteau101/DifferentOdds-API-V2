import asyncio
import re
import aiohttp
from Books.Bases.prediction_liquidity_base import PredictionLiquidityBase
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Settings.Models.prediction_liquidity_models import PredictionLiquidityStats, LiquidityData
from curl_cffi import AsyncSession as CurlAsyncSession

class FourCX(PredictionLiquidityBase):
    INVALID_LEAGUES = ["live", "custom", "superbowl", "nfc", "afc"] # Avoid these leagues or anything with these keywords

    def __init__(self):
        super().__init__(book_name="4cx")

    async def _get_leagues(self, session: CurlAsyncSession) -> dict:
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
            return name[0].lower() if name else "Unknown" ## Work on fixing.

        market_name = order.get("type", "")

        if ordinal:
            market_name = f"{ordinal} {market_name}"

        return market_name.lower()

    def _extract_order_details(self, game: dict) -> GameData | None:
        markets = self._get_markets(game)
        if not markets:
            return None

        league, ordinal = FourCX.remove_ordinal(game.get("league"), return_ordinal=True)

        modified_league = league.replace("-PROPS", "") if "props" in league.lower() else league

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

        game_date = game.get("start")

        team_keys = "_".join(team_list).replace(" ", "_")
        key = f"{league}_{team_keys}_{game_date}".lower()


        return GameData(
            game_key=key,
            start_date=game_date,
            league=modified_league,
            team_data=TeamData(
                team_a=team_list[0],
                team_b=team_list[1] if len(team_list) == 2 else None,
            ),
            odds=[
                PredictionLiquidityStats(
                    market=self._configure_market_name(ordinal=ordinal, event_name=game.get("eventName"), order=order, is_player_prop=True if "props" in league.lower() else False),
                    bet_team=FourCX.remove_ordinal(teams.get(order.get("participantID"))),
                    bet_type=order.get("OU"),
                    line=order.get("line"),
                    bet_player=game.get("eventName").split("(")[0].title().strip() if "props" in league.lower() else None,
                    player_team=teams.get(order.get("participantId")) if "props" in league.lower() else None,
                    future=False,
                    liquidity_data=[
                        LiquidityData(
                            odds_format=OddsFormat(american_odds=order.get("odds")),
                            liquidity=order.get("sumUntaken"),
                            is_best=True if index == 0 else False,
                            additional_information={}
                        )
                    ]
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

    async def load_auth(self) -> str:
        """Retrieve the authentication token from Redis"""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("4cx_auth_token")

    async def run_book(self):
        auth_token = await self.load_auth()

        if not auth_token:
            return None

        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            self.book_data.headers["Authorization"] = auth_token
            raw_leagues = await self._get_leagues(session)
            if not raw_leagues or not raw_leagues.get("data", {}).get("availableLeagues"):
                return None

            leagues = raw_leagues.get("data", {}).get("availableLeagues", [])
            leagues = self._filter_leagues(leagues)

            orders = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("orders"),
                    headers=self.book_data.headers,
                    method="POST",
                    json={"leagueRequested": league}
                )
                for league in leagues
            ]

            order_results = await asyncio.gather(*orders)

            game_data = {}

            for order in order_results:
                if not order or not order.get("data"):
                    continue

                for game in order.get("data", {}).get("games", []):
                    data = self._extract_order_details(game)
                    if data:
                        key = data.game_key
                        if key in game_data:
                            game_data[key].odds.extend(data.odds)
                        else:
                            game_data[key] = data


            game_list = list(game_data.values())
            mapped_data = await self.map_runner(session=session, sportsbook_data=game_list)
            print(mapped_data)
            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data


if __name__ == "__main__":
    book = FourCX()
    asyncio.run(book.run_book())