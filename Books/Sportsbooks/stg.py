import asyncio
import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
import aiohttp
from Books.Bases.pph_base import PPHBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.request_caller import SportbookRequestType

class STG(PPHBookBase):
    VALID_LEAGUES = ["NFL", "NBA", "MLB", "NHL", "NCAA"]

    def __init__(self):
        super().__init__(book_name="stg", request_type=SportbookRequestType.ASYNC)

    def get_cookies(self) -> dict:
        """Returns the cookies after logging in."""
        payload = {
            "txtAccessOfCode": os.getenv("STG_USERNAME"),
            "txtAccessOfPassword": os.getenv("STG_PASSWORD"),
            "button": ""
        }

        additional_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx",
        }

        return self.pph_login_helper(
            payload=payload,
            sportsbook_name="stg",
            login_key_word_check=".AITQKIAUT",
            additional_headers=additional_headers
        )

    def yield_sport_ids(self, results: list | tuple) -> Iterable:
        """Yields sport ID data structure from raw results."""
        for result_list in results:
            raw = result_list.get("d")
            if not raw:
                continue

            for data in json.loads(raw):
                yield data

    def format_league(self, league_name) -> str:
        """Format the league if there is a spaces, we only want the first item between spaces"""
        if " " in league_name:
            return league_name.split(" ")[0]

        return league_name

    def ordinal(self, name) -> str:
        num = int(name)
        if 10 <= num % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
        return f"{num}{suffix}"

    def ordinal_map(self, period_name: str, market_name: str) -> str:
        if not period_name:
            return market_name

        first_digit = re.search(r'\d', period_name).group()
        first_letter = re.search(r'[A-Za-z]', period_name).group()

        suffix = self.ordinal(first_digit)

        mapper = {
            "Q": "Quarter",
            "H": "Half",
        }

        return f"{suffix} {mapper.get(first_letter.upper(), market_name)} {market_name}"

    @staticmethod
    def get_line(line_str: str, include_direction: bool = True) -> tuple:
        raw_line = line_str.split(" ")[0]

        if not raw_line:
            return None, None

        if include_direction:
            direction = "over" if raw_line[0] == "o" else "under"
        else:
            direction = None

        if "½" in raw_line:
            line = raw_line[1:].replace("½", ".5")
        else:
            line = raw_line[1:]

        return line, direction

    def _get_team_total(self, team_total_data: dict, team_name:str) -> dict:
        if not team_total_data:
            return {}

        line, direction = STG.get_line(team_total_data.get("line"))
        return {
            "bet_team": team_name,
            "market": "Team Total",
            "bet_type": direction,
            "line": line,
            "american_odds": team_total_data.get("odds", {}).get("OddsValue"),
        }

    def _extract_markets(self, game_data: dict, league: str) -> GameData | dict:
        # If / not in date and time = Today else format 11/16
        if game_data.get("offline") or not game_data.get("sides"):
            return {}

        raw_game_date = game_data.get("dateandtime")
        if "AM" in raw_game_date or "PM" in raw_game_date:
            formatted_time = datetime.strptime(raw_game_date, "%I:%M %p").time()
            formatted_date = datetime.combine(date.today(), formatted_time, tzinfo=ZoneInfo("America/Chicago"))
            utc_date = formatted_date.astimezone(timezone.utc)
            game_date = utc_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            formatted_date = datetime.strptime(raw_game_date, "%m/%d").replace(year=datetime.now().year).date()
            game_date = formatted_date.strftime("%Y-%m-%dT00:00:00Z")

        raw_teams = game_data.get("teams").split(" - ")
        if len(raw_teams) == 2:
            team_a = raw_teams[1].strip()
            team_b = raw_teams[0].strip()
        else:
            team_a = game_data.get("teams").strip()
            team_b = ""

        key = STG.generate_key([team_a, team_b, game_date])

        odds_data = GameData(
            start_date=game_date,
            game_key=key,
            league=league,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
            ),
            odds=[]
        )

        for side in game_data.get("sides", []):
            team = side.get("name")
            if side.get("moneyline"):
                moneyline_dict = side.get("moneyline")
                american_odds = moneyline_dict.get("odds",{}).get("OddsValue")

                if not american_odds:
                    continue

                odds_data.odds.append(SportsbookStats(
                    bet_team=team,
                    future=False, # Will need to look into this.
                    market=self.ordinal_map(game_data.get("periodname"), "Moneyline"),
                    bet_type=None,
                    line=None,
                    odds_format=OddsFormat(american_odds=american_odds)
                ))

            if side.get("spread"):
                spread_dict = side.get("spread")
                line, _ = STG.get_line(spread_dict.get("line"), include_direction=False)

                american_odds = spread_dict.get("odds", {}).get("OddsValue")
                if not american_odds:
                    continue

                odds_data.odds.append(SportsbookStats(
                    bet_team=team,
                    future=False,  # Will need to look into this.
                    market=self.ordinal_map(game_data.get("periodname"), "Spread"),
                    bet_type=None,
                    line=line,
                    odds_format=OddsFormat(american_odds=american_odds)
                ))

            if side.get("total"):
                total_dict = side.get("total")
                line, direction = STG.get_line(total_dict.get("line"))

                american_odds = total_dict.get("odds", {}).get("OddsValue")
                if not american_odds:
                    continue

                odds_data.odds.append(SportsbookStats(
                    bet_team=None,
                    future=False,  # Will need to look into this.
                    market=self.ordinal_map(game_data.get("periodname"), "Total"),
                    bet_type=direction,
                    line=line,
                    odds_format=OddsFormat(american_odds=american_odds)
                ))


            if side.get("ttunder"):
                data = self._get_team_total(side.get("ttunder"), team)

                if not data.get("american_odds"):
                    continue

                odds_data.odds.append(SportsbookStats(
                    bet_team=team,
                    future=False,  # Will need to look into this.
                    market=self.ordinal_map(game_data.get("periodname"), "Team Total"),
                    bet_type=data.get("bet_type"),
                    line=data.get("line"),
                    odds_format=OddsFormat(american_odds=data.get("american_odds"))
                ))

                # odds_data.get("odds").append(data)

            if side.get("ttover"):
                data = self._get_team_total(side.get("ttover"), team)

                if not data.get("american_odds"):
                    continue

                odds_data.odds.append(SportsbookStats(
                    bet_team=team,
                    future=False,  # Will need to look into this.
                    market=self.ordinal_map(game_data.get("periodname"), "Team Total"),
                    bet_type=data.get("bet_type"),
                    line=data.get("line"),
                    odds_format=OddsFormat(american_odds=data.get("american_odds"))
                ))

        return odds_data

    def _create_special_payload(self, sport_value: str) -> dict:
        return {
            "value": sport_value,
            "iscontest": False,
            "wagerTypeInfo": "1",
            "isRefresh": False,
            "contestOrderBy": 0,
            "isContestRelated": False,
            "specialEventId": 0,
            "getOnlyPeriods": False,
        }

    async def run_book(self):
        cookies = self.get_cookies()

        if not cookies:
            return

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Referer": "https://bettheguys.com/Player/main.aspx",
        }

        new_headers = {**self.book_data.headers, **headers}

        async with aiohttp.ClientSession(cookies=cookies, headers=new_headers) as session:
            raw_league_ids = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_list_url"),
                headers=new_headers,
                payload={
                    "wagerTypeValue": "1"
                },
                method="POST",
            )

            print(raw_league_ids)

            league_ids = json.loads(raw_league_ids.get("d"))

            if not league_ids:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="mapping_failure",
                    message="No mapped IDs were found.",
                    level="error"
                )

                return None

            league_ids = set(
                sportId.get("IdSport")
                for league in league_ids.values()
                for sportId in league.get("SportsList", [])
                if sportId
            )

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("league_section"),
                    payload={
                        "idMainHeader": str(league_id),
                        "wagerTypeValue": "1"
                    },
                    headers = new_headers,
                    method = "POST",
                )

                for league_id in league_ids
            ]

            raw_results = await asyncio.gather(*tasks)

            league_data = [
                {
                    "sport_id": child.get("IdSport"),
                    "sport_value": child.get("Value"),
                    "league": self.format_league(sport_info.get("Name"))
                }
                for sport_info in self.yield_sport_ids(results=raw_results)
                for child in sport_info.get("Children", [])
                if child and self.format_league(sport_info.get("Name")) in self.VALID_LEAGUES
            ]

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("game_markets"),
                    payload=self._create_special_payload(league.get("sport_value")),
                    headers=new_headers,
                    method="POST",
                )

                for league in league_data
            ]

            results = await asyncio.gather(*tasks)

            game_results = []

            for league, result in zip(league_data, results):
                if not result:
                    continue

                result = json.loads(result.get("d"))
                league_name = league.get("league")

                for game in result.get("lines", []):
                    if game:
                        extracted = self._extract_markets(game, league=league_name)

                        if extracted and hasattr(extracted, "odds") and extracted.odds:
                            game_results.append(extracted)

            mapped_data = await self.map_runner(session=session, sportsbook_data=game_results)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data

if __name__ == "__main__":
    stg = STG()
    asyncio.run(stg.run_book())