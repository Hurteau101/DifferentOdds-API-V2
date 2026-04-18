import asyncio
import os
import re
from functools import reduce
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from Authentication.sts_auth import STSAuth
from Books.Bases.pph_base import PPHBookBase
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.proxy_manger import ProxyManager
from Utils.request_caller import SportbookRequestType
from curl_cffi import AsyncSession as CurlAsyncSession
import json
from datetime import datetime, timezone

class STS(PPHBookBase):
    VALID_CATEGORIES = ["football", "baseball", "hockey", "basketball", "college football", "college basketball"]
    # VALID_LEAGUES = ["NBA", "MLB", "NHL", "NHL-OTINCLUDED", "NHL", "CBB", "CFB", "NCAA/USA/INT-OTINCLUDED"]
    VALID_LEAGUES = ["NBA"]
    LEAGUE_NAME_REPLACER = ["-", "otincluded", "/usa/int"]

    def __init__(self):
        super().__init__(book_name="sts", request_type=SportbookRequestType.SPOOF)
        self.retry = 0

    async def load_cookies(self) -> dict | None:
        """Extracts the cookies from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("sts_cookies")

    async def load_proxy(self) -> dict | None:
        """Extracts the proxy from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("sts_proxy")

    @staticmethod
    def clean_return(api_data: dict, contains_d: bool = True) -> dict:
        """Cleans the returned API response, due to it being a string and having extra spaces"""
        if not api_data:
            return {}

        data = api_data.get("d", '') if contains_d else api_data
        if isinstance(data, dict):
            return data

        if isinstance(data, str):
            cleaned = data.replace("\n", "").replace(" ", "").strip()
            return json.loads(cleaned)

        raise ValueError("API response is not in the expected format. Expected a dictionary or a string that can be converted to a dictionary.")

    def build_markets(self, market: dict, league_map: dict, date_month: datetime, backup_period: str) -> list:
        game_list = []

        for line in market.get("lines", []):
            period = line.get("periodname", "N/A") or backup_period

            if line.get("offline") or not line.get("sides"):
                continue

            teams = self._extract_teams(line.get("sides", []))
            if not teams:
                continue

            game_time = line.get("dateandtime", "")
            formatted_time = datetime.strptime(game_time, "%I:%M%p").time()
            combined_date = datetime.combine(date_month.date(), formatted_time, tzinfo=ZoneInfo("America/Chicago"))
            utc_time = combined_date.astimezone(timezone.utc).replace(tzinfo=None)  # Remove timezone info after conversion
            start_date = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            game_key = self.generate_key([teams.team_a, teams.team_b, start_date]) if teams else None
            league = league_map.get(line.get("idsport"), "unknown league")

            game_data = GameData(
                start_date=start_date,
                league=league,
                team_data=teams,
                odds=[],
                game_key=game_key
            )

            for side in line.get("sides", []):

                # Find key name, ensure its a dict and has a line value in that dict, or it wouldn't be considered a market.
                market_names = set((key for key, value in side.items() if isinstance(value, dict) and "line" in value))
                if not market_names:
                    continue

                for market_name in market_names:
                    odds = self.market_controller(market_name=market_name, market_data=side.get(market_name, {}), team=side.get("name", ""),
                                                  league=league, period=period)
                    if odds:
                        game_data.odds.append(odds)


            if game_data.odds:
                game_list.append(game_data)

        return game_list

    def _extract_teams(self, sides: list) -> TeamData | None:
        if len(sides) != 2:
            return None

        return TeamData(
            team_a=sides[0].get("name", ""),
            team_b=sides[1].get("name", "")
        )

    def _moneyline_type(self, market_data: dict, market_name: str, **kwargs) -> SportsbookStats:
        return SportsbookStats(
            market=market_name,
            bet_team=market_data.get("teams", ""),
            line=None,
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=float(market_data.get("odds", {}).get("OddsValue", 0)))
        )

    def _total_type(self, market_data: dict, market_name: str, **kwargs) -> SportsbookStats | None:
        raw_line = self.line_formatter(market_data.get("line", ''))

        if not raw_line:
            return None

        match = re.match(
            r"^([ou])(\d+(?:\.(?:0|00|5|50|25|75))?)(?:[+-]?\d{3,4})?$",
            raw_line
        )

        if match:
            bet_type = "over" if match.group(1) == "o" else "under"
            line = float(match.group(2))

            team = kwargs.get("team", None)

            return SportsbookStats(
                market=market_name,
                bet_team=team,
                line=line,
                bet_type=bet_type,
                future=False,
                odds_format=OddsFormat(american_odds=float(market_data.get("odds", {}).get("OddsValue", 0)))
            )

        return None

    def line_formatter(self, line: str) -> str:
        return line.replace("½", ".5").replace("¼", ".25").replace("¾", ".75")

    def _spread_type(self, market_data: dict, market_name: str, **kwargs) -> SportsbookStats | None:
        raw_line = self.line_formatter(market_data.get("line", ''))

        if not raw_line:
            return None

        line = re.match(r"([+-]?\d*\.?\d+)", raw_line).group()

        league = kwargs.get("league", "")

        if league == "mlb":
            market_name = "run line"
        elif league == "nhl":
            market_name = "puck line"


        return SportsbookStats(
            market=market_name,
            bet_team=kwargs.get("team"),
            line=float(line) if line else None,
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=float(market_data.get("odds", {}).get("OddsValue", 0)))
        )


    def market_controller(self, market_name: str, market_data: dict, **kwargs) -> SportsbookStats | None:
        """
        Controller function to determine which market builder to use based on the mapped market name.
        These functions use the _ convention as we don't want to inherit/override the base functions (money_type, spread_type, etc), that are similar on other PPHs.
        """
        mapper = {
            "moneyline": self._moneyline_type,
            "spread": self._spread_type,
            "total": self._total_type,
            "team total": self._total_type,
        }

        market_mapper = {
            "ttover": "team total",
            "ttunder": "team total"
        }

        market_name = market_mapper.get(market_name.lower(), market_name.lower())

        handler = mapper.get(market_name.lower())

        if not handler:
            return None

        period = kwargs.get("period", "").lower()
        if period != "game":
            market_name = f"{period} {market_name}"

        return handler(market_data=market_data, market_name=market_name, **kwargs)

    # Backup Auth since the site has bugs, where the cookie will no longer be valid, even if it was issued.
    # Happens randomly. So if we get no data back, we will try to refresh the cookie and try again once.
    async def back_up_auth_runner(self):
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sts = STSAuth()
            await sts.run_scheduler(session=session, redis_instance=redis_instance)
            self.retry += 1

    async def run_book(self):
        cookies = await self.load_cookies()
        proxy = await self.load_proxy()

        if not cookies or not proxy:
            return

        async with CurlAsyncSession(impersonate="safari15_5", cookies=cookies) as session:
            proxy_manager = ProxyManager(self.api_caller)
            proxy_manager.proxies = [proxy]

            raw_league_data = await proxy_manager.api_caller(
                url=self.book_data.url.get("category_url"),
                headers=self.book_data.headers,
                payload={"wagerTypeValue": 1},
                method="POST",
                session=session,
                book_name=self.book_data.name,
                parse_json=True
            )

            if not raw_league_data:
                # if self.retry < 3:
                #     print("Failed to fetch data, retry #", self.retry + 1)
                #     await self.back_up_auth_runner()
                #     await self.run_book()
                return

            sports_ids = set(
                category.get("IdSport")
                for category in self.clean_return(raw_league_data).get("Sports").get("SportsList", [])
                if category.get("Name", '').lower() in self.VALID_CATEGORIES
            )

            league_name_tasks = [
                proxy_manager.api_caller(
                    url=self.book_data.url.get("league_url"),
                    headers=self.book_data.headers,
                    payload={"idMainHeader":str(sport_id), "wagerTypeValue": "1"},
                    method="POST",
                    session=session,
                    book_name=self.book_data.name,
                    parse_json=True
                )

                for sport_id in sports_ids
            ]

            semaphore = asyncio.Semaphore(2)

            league_results = await asyncio.gather(*[
                self.post_with_semaphore(semaphore, task) for task in league_name_tasks
            ])

            # league_results = await asyncio.gather(*league_name_tasks)
            cleaned_leagues = [self.clean_return(result) for result in league_results]

            league_map = {
                league.get("IdSport"): reduce(lambda name, remove: name.replace(remove, ""), self.LEAGUE_NAME_REPLACER, league.get("Name", "").lower())
                for result in cleaned_leagues
                if result
                for league in result
            }

            league_ids = [
                children.get("Value")
                for result in cleaned_leagues
                if result
                for league in result
                for children in league.get("Children", [])
                if league.get("Name", "").upper() in self.VALID_LEAGUES
            ]

            market_tasks = [
                proxy_manager.api_caller(
                    url=self.book_data.url.get("market_url"),
                    headers=self.book_data.headers,
                    payload={
                        "value":str(market),
                        "iscontest":False,
                        "wagerTypeInfo":"1",
                        "isRefresh":False,
                        "contestOrderBy":0,
                        "isContestRelated":False,
                        "specialEventId":0,
                        "getOnlyPeriods":False
                    },
                    method="POST",
                    session=session,
                    book_name=self.book_data.name,
                    parse_json=True
                )

                for market in league_ids
            ]

            market_results = await asyncio.gather(*[
                self.post_with_semaphore(semaphore, task) for task in market_tasks
            ])

            # market_results = await asyncio.gather(*market_tasks)
            cleaned_markets = [self.clean_return(result) for result in market_results]

            event_data = {}

            for cleaned in cleaned_markets:
                # First index contains some game information, where the rest of the indexes don't.
                first_index_line = cleaned.get("lines", [])[0] if cleaned.get("lines") else None

                if not first_index_line:
                    continue

                date_month = first_index_line.get("dateandtime", "")
                current_year = datetime.now().year # There is no year in there API data, so use this year.
                date_month_dt = datetime.strptime(f"{date_month}-{current_year}", "%m/%d-%Y")
                backup_period = first_index_line.get("periodname", 'N/A')

                game_data = self.build_markets(market=cleaned, league_map=league_map, date_month=date_month_dt, backup_period=backup_period)
                if not game_data:
                    continue

                for game in game_data:
                    self.add_to_events(event_data, game, GameData)

            sts_data = list(event_data.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=sts_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data


if __name__ == "__main__":
    ace = STS()
    asyncio.run(ace.run_book())