import asyncio
import os
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import aiohttp
from urllib.parse import urlencode
from Books.Bases.pph_base import PPHBookBase
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import TeamData, GameData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.request_caller import SportbookRequestType


class Buckeye2(PPHBookBase):
    VALID_LEAGUES = ["NBA", "MLB", "NHL", "NFL", "CBB", "CFB", "NCAA BASKETBALL"]

    def __init__(self):
        super().__init__(book_name="buckeye2", request_type=SportbookRequestType.ASYNC)

    async def load_auth(self) -> str | None:
        """Extracts the cookies from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("buckeye_2_auth_token")

    @staticmethod
    def name_mapper(market_name: str, odds_key: str, base_market_mapper: dict, **kwargs) -> str:
        mapper = {
            "moneyline1": "Moneyline",
            "moneyline2": "Moneyline",
            "spreadadj1": "Spread",
            "spreadadj2": "Spread",
            "ttlptsadj1": "Total",
            "ttlptsadj2": "Total",
            "team1ttlptsadj1": "Team Total",
            "team1ttlptsadj2": "Team Total",
            "team2ttlptsadj1": "Team Total",
            "team2ttlptsadj2": "Team Total",
        }

        period_description = kwargs.get("period_description", "").lower()
        raw_market_name = mapper.get(odds_key.lower(), odds_key)

        return f"{period_description} {raw_market_name}" if period_description !=  "game" else raw_market_name

    def calulate_spread_buy_points(self, spread_line: float | int, spread_odds: float,
                                   buy_points_amount: float | int, buy_points_max: float | int,
                                   market_name: str, bet_team: str) -> list | None:
        """
        Calculates the new spread line and odds after applying the buy points for spread markets.
        :param spread_line: The original spread line.
        :param spread_odds: The original spread odds.
        :param buy_points_amount: The amount of buy points to apply.
        :param buy_points_max: The maximum amount of buy points allowed.
        :param market_name: The name of the market for which the buy points are being calculated.
        :param bet_team: The team for which the buy points are being calculated.
        """
        if not buy_points_amount or not buy_points_max:
            return None

        odds_list = []

        for step in range(buy_points_max + 1):
            new_spread = spread_line + (step * 0.5)
            if new_spread == spread_line:
                continue

            odds = spread_odds - (buy_points_amount * step)
            odds_list.append(SportsbookStats(
                market=market_name,
                bet_team=bet_team,
                line=new_spread,
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(odds)),
            ))

        return odds_list

    def calulate_total_buy_points(self, total_line: float | int, total_odds: float,
                                   buy_points_amount: float | int, buy_points_max: float | int,
                                   market_name: str, direction: str) -> list | None:
        """
        Calculates the new spread line and odds after applying the buy points for spread markets.
        :param total_line: The original total line.
        :param total_odds: The original total odds.
        :param buy_points_amount: The amount of buy points to apply.
        :param buy_points_max: The maximum amount of buy points allowed.
        :param market_name: The name of the market for which the buy points are being calculated.
        :param direction: The direction for the total market, either "over" or "under", which determines whether the total line increases or decreases with buy points.
        """
        if not buy_points_amount or not buy_points_max:
            return None

        odds_list = []

        for step in range(buy_points_max + 1):
            step_direction = step * -0.5 if direction.lower() == "over" else step * 0.5

            new_total = total_line + step_direction
            if new_total == total_line:
                continue

            odds = total_odds - (buy_points_amount * step)
            odds_list.append(SportsbookStats(
                market=market_name,
                bet_team=None,
                line=abs(float(new_total)),
                bet_type=direction,
                future=False,
                odds_format=OddsFormat(american_odds=float(odds)),
            ))

        return odds_list

    def spread_type(self, team_data: TeamData, game_data: dict, market_name: str, name_mapper_func: Callable,
                       home_spread_odds_name:str, away_spread_odds_name: str,
                    home_spread_value_name: str, away_spread_value_name: str,
                    base_market_mapper: dict, **kwargs) -> list:
        """
        Builds spread type markets for a given game and team data.
        :param team_data: The team data for the game, containing the team names.
        :param game_data: The game data containing the odds information.
        :param market_name: The modified description name.
        :param name_mapper_func: Function to help map market names.
        :param home_spread_odds_name: The key name for the home team spread odds in the game_data.
        :param away_spread_odds_name: The key name for the away team spread odds in the game_data.
        :param home_spread_value_name: The key name for the home team spread value in the game_data.
        :param away_spread_value_name: The key name for the away team spread value in the game_data.
        :param base_market_mapper: The market mapper to use for mapping the market name.
        """
        odds = []

        for team, line_key, odds_key in [
            (team_data.team_a, home_spread_value_name, home_spread_odds_name),
            (team_data.team_b, away_spread_value_name, away_spread_odds_name)
        ]:

            mapped_market_name = name_mapper_func(market_name=market_name, odds_key=odds_key, base_market_mapper=base_market_mapper, **kwargs)

            spread_odds = game_data.get(odds_key)
            spread_line = game_data.get(line_key)

            if not spread_odds or not spread_line:
                continue

            favourite_team = kwargs.get("favourite_team")

            spread_line = -abs(spread_line) if team == favourite_team else abs(spread_line)

            if not spread_odds or spread_line is None:
                continue

            odds.append(SportsbookStats(
                market=self.convert_spread_name(mapped_market_name, kwargs.get("league")),
                bet_team=team,
                line=float(spread_line),
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(spread_odds)),
            ))

        return odds

    def total_type(self, game_data: dict, market_name: str, **kwargs) -> list:
        """
        Builds total type markets.
        :keyword games: The outer game data container that contains the team names, as the game dict doesn't contain this information.
        :keyword name_mapper_func: Function to help map market names.
        :param game_data: The game data containing the odds information.
        :param market_name: The modified description name.
        """
        odds = []

        over_points_odds_name = kwargs.get("over_points_odds_name")
        under_points_odds_name = kwargs.get("under_points_odds_name")

        over_points_line_name = kwargs.get("over_points_line_name")
        under_points_line_name = kwargs.get("under_points_line_name", over_points_line_name)

        team_name = kwargs.get("team_name", None)

        for bet_type, line_key, odds_key in [("Over", over_points_line_name, over_points_odds_name), ("Under", under_points_line_name, under_points_odds_name)]:
            mapped_market_name = self.name_mapper(market_name=market_name, odds_key=odds_key, base_market_mapper={}, **kwargs)

            total_line = game_data.get(line_key)
            total_odds = game_data.get(odds_key)


            if not total_line or not total_odds:
                continue

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=team_name,
                line=abs(float(total_line)),
                bet_type=bet_type,
                future=False,
                odds_format=OddsFormat(american_odds=float(total_odds)),
            ))

        return odds


    def build_markets(self, event_data: dict, buy_points: dict | None):
        start_date = event_data.get("GameDateTime")
        eastern = ZoneInfo("America/New_York")
        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=eastern)
        modified_date = start_date_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

        team_data = TeamData(
            team_a=event_data.get("Team1ID"),
            team_b=event_data.get("Team2ID"),
        )

        game_data = GameData(
            start_date=modified_date,
            league=event_data.get("SportSubType", '').strip(),
            team_data=team_data,
            odds=[],
            game_key=self.generate_key([event_data.get("Team1ID"), event_data.get("Team2ID"), modified_date]),
        )

        game_data.odds.extend(self.moneyline_type(
            team_data=team_data,
            game_data=event_data,
            market_name="",
            name_mapper_func=self.name_mapper,
            home_odds_name="MoneyLine1",
            away_odds_name="MoneyLine2",
            base_market_mapper={},
            period_description=event_data.get("PeriodDescription", '')
        ))

        spread_odds = self.spread_type(
            team_data=team_data,
            game_data=event_data,
            market_name="",
            name_mapper_func=self.name_mapper,
            home_spread_odds_name="SpreadAdj1",
            away_spread_odds_name="SpreadAdj2",
            base_market_mapper={},
            home_spread_value_name="Spread", # Spread value goes both directions. Ex. +7 -> then there is -7
            away_spread_value_name="Spread",
            period_description=event_data.get("PeriodDescription", ''),
            favourite_team=event_data.get("FavoredTeamID"),
            league=event_data.get("SportSubType", '').strip()
        )

        if buy_points and buy_points.get("Spread") and event_data.get("PeriodDescription", '').lower() == "game":
            for odd in spread_odds:
                game_data.odds.extend(self.calulate_spread_buy_points(spread_line=odd.line, spread_odds=odd.odds_format.get("american_odds"),
                                                buy_points_amount=buy_points["Spread"]["amount"],
                                                buy_points_max=buy_points["Spread"]["max"], market_name=odd.market, bet_team=odd.bet_team))
                # print(additional_odds)
                # if additional_odds:
                #     game_data.odds.extend(self.convert_spread_name(additional_odds, game_data.league))

        game_data.odds.extend(spread_odds)

        total_odds = self.total_type(
            period_description=event_data.get("PeriodDescription", ''),
            game_data=event_data,
            market_name="",
            over_points_odds_name="TtlPtsAdj1",
            under_points_odds_name="TtlPtsAdj2", # Under is always 2.
            over_points_line_name="TotalPoints", # Points goes both directions always. We can just set over since it will be the same, and function will set it automatically.
        )

        if buy_points and buy_points.get("Total") and event_data.get("PeriodDescription", '').lower() == "game":
            for odd in total_odds:
                additional_odds = self.calulate_total_buy_points(
                    total_line=odd.line, total_odds=odd.odds_format.get("american_odds"),
                    buy_points_amount=buy_points["Total"]["amount"], buy_points_max=buy_points["Total"]["max"],
                    market_name=odd.market, direction=odd.bet_type
                )

                if additional_odds:
                    game_data.odds.extend(additional_odds)

        game_data.odds.extend(total_odds)

        # Home Team Team Total
        for index, team in enumerate([team_data.team_a, team_data.team_b], start=1):
            game_data.odds.extend(self.total_type(
                period_description=event_data.get("PeriodDescription", ''),
                game_data=event_data,
                market_name="",
                over_points_odds_name=f"Team{index}TtlPtsAdj1",
                under_points_odds_name=f"Team{index}TtlPtsAdj2", # Under is always 2.
                over_points_line_name=f"Team{index}TotalPoints", # Points goes both directions always. We can just set over since it will be the same, and function will set it automatically.
                team_name=team
            ))

        return game_data

    # This is used for the dropdowns on the website.
    async def get_buy_points(self, username: str, auth_token: str, session: aiohttp.ClientSession, sport_type: str, sport_subtype: str):
        return await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("point_group_url"),
            method=self.book_data.method,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                "Authorization": f"Bearer {auth_token}"
            },

            payload=urlencode({
                "customerID": username,
                "wagerType": "Straight",
                "sportType": sport_type,
                "sportSubType": sport_subtype,
                "RRO": ''
            })
        )



    async def market_caller(self, session: aiohttp.ClientSession, username: str, auth_token: str, league: dict):
        market_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("market_url"),
            headers={
                **self.book_data.headers,
                "Authorization": f"Bearer {auth_token}"
            },
            method=self.book_data.method,
            payload=urlencode({
                "customerID": username,
                "operation": "Get_LeagueLines2",
                "sportType": league.get("SportType"),
                "sportSubType": league.get("SportSubType"),
                "period": league.get("PeriodDescription"),
                "hourFilter": "0",
                "propDescription": "",
                "wagerType": "Straight",
                "keyword": "",
                "office": "WAGERHOME",
                "correlationID": "",
                "periodNumber": league.get("PeriodNumber"),
                "periods": "0",
                "rotOrder": "0",
                "placeLateFlag": "false",
                "RRO": "1",
                "agentSite": "0",
            })
        )

        sport_type = league.get("SportType")
        if sport_type in ["BASKETBALL", "FOOTBALL"]:
            buy_points = await self.get_buy_points(username=username, auth_token=auth_token, session=session,
                                             sport_type=league.get("SportType"), sport_subtype=league.get("SportSubType"))

            if buy_points and sport_type in ["BASKETBALL", "FOOTBALL"]:
                buy_points_key = buy_points.get("BuyPoints", {})
                market_data["buypoints"] = {
                    "Spread": {
                        "amount": buy_points_key.get("SpreadBuy", 0),
                        "max": buy_points_key.get("SpreadBuyMax", 0)
                    },
                    "Total": {
                        "amount": buy_points_key.get("TotalBuy", 0),
                        "max": buy_points_key.get("TotalBuyMax", 0)
                    }
                }

        return market_data


    async def run_book(self):
        username = os.getenv("BUCKEYE_2_USERNAME")

        if not username:
            raise ValueError("Missing required environment variable: BUCKEYE_2_USERNAME")

        async with aiohttp.ClientSession() as session:
            auth_token = await self.load_auth()
            if not auth_token:
                print("Auth Expired")
                return


            raw_leagues = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_url"),
                method=self.book_data.method,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://wwcd.me',
                    'Connection': 'keep-alive',
                    'Referer': 'https://wwcd.me/sports.html?v=1775430461341',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'TE': 'trailers',
                    "Authorization": f"Bearer {auth_token}"
                },
                # Ensure its urlencode, or pass a string, or else you won't get the proper data back.
                payload=urlencode({
                    "customerID": username,
                    "wagerType": "Straight",
                    "office": "WAGERHOME",
                    "placeLateFlag": "false",
                    "operation": "Get_SportsLeagues",
                    "RRO": 1,
                    "agentSite": 0
                })
            )

            leagues = [
                league
                for league in raw_leagues.get("Leagues", [])
                if league.get("SportSubTypeDisplay", '').upper() in self.VALID_LEAGUES
            ]

            raw_data = [
                self.market_caller(
                    session=session,
                    username=username,
                    auth_token=auth_token,
                    league=league
                )
                for league in leagues
            ]

            results = await asyncio.gather(*raw_data)

            event_data = {}

            for result in results:
                buy_points = result.get("buypoints", None)
                for line in result.get("Lines", []):
                    game_data = self.build_markets(event_data=line, buy_points=buy_points)
                    if game_data:
                        self.add_to_events(event_data, game_data, GameData)

            buckeye_2_data = list(event_data.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=buckeye_2_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data


if __name__ == "__main__":
    metallic = Buckeye2()
    asyncio.run(metallic.run_book())


