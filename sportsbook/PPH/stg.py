import json
import os
import re
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from Settings.Sportsbook_Settings.sportsbook_model import GameData, TeamData, Markets
import aiohttp
import asyncio
from Settings.pph_base import PPHBookBase
from Settings.book_base import SportbookRequestType
import json

class STG(PPHBookBase):
    VALID_LEAGUES = ["NFL", "NBA", "MLB", "NHL", "NCAA"]

    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="stg")

    def _get_cookies(self):
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

        return self._pph_login(
            payload=payload,
            sportsbook_name="stg",
            login_key_word_check=".AITQKIAUT",
            additional_headers=additional_headers
        )

    @staticmethod
    def get_line(line_str: str, include_direction: bool = True):
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

    def _get_team_total(self, team_total_data: dict, team_name:str):
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

    def ordinal(self, n):
        n = int(n)
        if 10 <= n % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"

    def ordinal_map(self, period_name: str, market_name: str):
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




    def _extract_markets(self, game_data, league):
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

        team_key = self._generate_key([team_a, team_b, game_date])

        odds_data = GameData(
            book_name="stg",
            start_date=game_date,
            league=league,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
                team_key=team_key

            ),
            event_name=f"{team_a} vs. {team_b}",
            odds=[]
        )

        for side in game_data.get("sides", []):

            team = side.get("name")
            if side.get("moneyline"):
                moneyline_dict = side.get("moneyline")
                american_odds = moneyline_dict.get("odds",{}).get("OddsValue")

                if not american_odds:
                    continue

                odds_data.odds.append(Markets(
                    bet_team=team,
                    market=self.ordinal_map(game_data.get("periodname"), "Moneyline"),
                    bet_type=None,
                    line=None,
                    american_odds=american_odds
                ))

            if side.get("spread"):
                spread_dict = side.get("spread")
                line, _ = STG.get_line(spread_dict.get("line"), include_direction=False)

                american_odds = spread_dict.get("odds", {}).get("OddsValue")
                if not american_odds:
                    continue

                odds_data.odds.append(Markets(
                    bet_team=team,
                    market=self.ordinal_map(game_data.get("periodname"), "Spread"),
                    bet_type=None,
                    line=line,
                    american_odds=american_odds
                ))

            if side.get("total"):
                total_dict = side.get("total")
                line, direction = STG.get_line(total_dict.get("line"))

                american_odds = total_dict.get("odds", {}).get("OddsValue")
                if not american_odds:
                    continue

                odds_data.odds.append(Markets(
                    bet_team=None,
                    market=self.ordinal_map(game_data.get("periodname"), "Total"),
                    bet_type=direction,
                    line=line,
                    american_odds=american_odds,
                ))


            if side.get("ttunder"):
                data = self._get_team_total(side.get("ttunder"), team)

                if not data.get("american_odds"):
                    continue

                odds_data.odds.append(Markets(
                    bet_team=team,
                    market=self.ordinal_map(game_data.get("periodname"), "Team Total"),
                    bet_type=data.get("bet_type"),
                    line=data.get("line"),
                    american_odds=data.get("american_odds"),
                ))

                # odds_data.get("odds").append(data)

            if side.get("ttover"):
                data = self._get_team_total(side.get("ttover"), team)

                if not data.get("american_odds"):
                    continue

                odds_data.odds.append(Markets(
                    bet_team=team,
                    market=self.ordinal_map(game_data.get("periodname"), "Team Total"),
                    bet_type=data.get("bet_type"),
                    line=data.get("line"),
                    american_odds=data.get("american_odds"),
                ))

                # odds_data.get("odds").append(data)

        return odds_data

    def _create_special_payload(self, sport_value: str):
        return (
            f"{{\"value\":\"{sport_value}\","
            f"\"iscontest\":false,"
            f"\"wagerTypeInfo\":\"1\","
            f"\"isRefresh\":false,"
            f"\"contestOrderBy\":0,"
            f"\"isContestRelated\":false,"
            f"\"specialEventId\":0,"
            f"\"getOnlyPeriods\":false}}"
        )

    def _format_league(self, league_name):
        if " " in league_name:
            return league_name.split(" ")[0]

        return league_name


    async def run_book(self):
        cookies = self._get_cookies()

        if not cookies:
            return

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Referer": "https://bettheguys.com/Player/main.aspx",
        }

        new_headers = {**self.book_data.headers, **headers}
        payload = '{"wagerTypeValue":"1"}'
        # payload = "{\"idMainHeader\":\"4\",\"wagerTypeValue\":\"1\"}"

        async with aiohttp.ClientSession(cookies=cookies, headers=new_headers) as session:
            league_ids = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_list_url"),
                headers=new_headers,
                data=payload,
                method="POST",
                use_parser=True,
                key_name="d",
                is_inner=True
            )

            if not league_ids:
                return

            league_ids = set(
                sportId.get("IdSport")
                for league in league_ids.values()
                for sportId in league.get("SportsList", [])
                if sportId
            )

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("league_section"),
                    data=f'{{"idMainHeader":"{league_id}","wagerTypeValue":"1"}}',
                    headers = new_headers,
                    method = "POST",
                    use_parser = True,
                    key_name = "d",
                    is_inner = True
                )

                for league_id in league_ids
            ]

            results = await asyncio.gather(*tasks)

            # Added league check due to amount of data.
            league_data = [
                {
                    "sport_id": children.get("IdSport"),
                    "sport_value": children.get("Value"),
                    "league": self._format_league(result.get("Name")),
                }

                for result_list in results
                for result in result_list
                for children in result.get("Children", [])
                if children and self._format_league(result.get("Name")) in self.VALID_LEAGUES
            ]


            tasks = [
               self.api_caller(
                    session=session,
                    url=self.book_data.url.get("game_markets"),
                    data=self._create_special_payload(league.get("sport_value")),
                    headers=new_headers,
                    method="POST",
                    use_parser=True,
                    key_name="d",
                    is_inner=True
                )

                for league in league_data
            ]

            results = await asyncio.gather(*tasks)

            game_results = []

            for league, result in zip(league_data, results):
                if not result:
                    continue

                league_name = league.get("league")

                for game in result.get("lines", []):
                    if game:
                        extracted = self._extract_markets(game, league=league_name)

                        if extracted and hasattr(extracted, "odds") and extracted.odds:
                            game_results.append(extracted)

            return await self._database_mapper(game_results)

if __name__ == "__main__":
    stg = STG()
    asyncio.run(stg.run_book())