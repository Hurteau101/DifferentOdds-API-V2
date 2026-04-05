import json
from typing import Callable

import requests
from bs4 import BeautifulSoup
from curl_cffi.requests import Session
from Books.Bases.book_base import BookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.base_models import TeamData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.request_caller import SportbookRequestType
from Books.Bases.sportsbook_base import SportsbooksBookBase


class PPHBookBase(SportsbooksBookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(book_name=book_name, request_type=request_type)

    def spread_type(self, team_data: TeamData, game_data: dict, market_name: str, name_mapper_func: Callable,
                       home_spread_odds_name:str, away_spread_odds_name: str,
                    home_spread_value_name: str, away_spread_value_name: str,
                    base_market_mapper: dict) -> list:
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
            mapped_market_name = name_mapper_func(market_name=market_name, odds_key=odds_key, base_market_mapper=base_market_mapper)

            spread_odds = game_data.get(odds_key)
            spread_line = game_data.get(line_key)


            if not spread_odds or spread_line is None:
                continue

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=team,
                line=float(spread_line),
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(spread_odds)),
            ))

        return odds


    def moneyline_type(self, team_data: TeamData, game_data: dict, market_name: str, name_mapper_func: Callable,
                       home_odds_name:str, away_odds_name: str, base_market_mapper: dict) -> list:
        """
        Builds moneyline type markets for a given game and team data.
        :param team_data: The team data for the game, containing the team names.
        :param game_data: The game_data containing the odds information.
        :param market_name: The market name.
        :param name_mapper_func: Function to help map market names.
        :param home_odds_name: The key name for the home team odds in the game_data.
        :param away_odds_name: The key name for the away team odds in the game_data.
        :param base_market_mapper: The market mapper to use for mapping the market name.
        """
        odds = []

        for team, odds_key in [(team_data.team_a, home_odds_name), (team_data.team_b, away_odds_name)]:
            mapped_market_name = name_mapper_func(market_name=market_name, odds_key=odds_key, base_market_mapper=base_market_mapper)

            moneyline_odds = game_data.get(odds_key)
            if not moneyline_odds:
                continue

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=team,
                line=None,
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(moneyline_odds)),
            ))

        return odds


    # Other books can override this function as needed, as different books have different ways of mapping.
    def total_type(self, game_data: dict, market_name: str, **kwargs) -> list:
        """Builds total type markets"""
        return []

    @staticmethod
    def name_mapper(market_name: str, odds_key: str, base_market_mapper: dict) -> str:
        """
        Maps the description name and odds key to a market name
        :param market_name: The market name.
        :param odds_key: The key name for the odds key.
        :param base_market_mapper: The market mapper to use for mapping the market name (Base: Spread, Moneyline, Total).
        """
        ordinal_suffix_markets = ["1h", "2h", "1p", "2p", "3p", '1q', '2q', '3q', '4q']

        irregular_ordinal_markets = ["3p regulation", '3rd innings', '7th inning', '1st 5 innings', '1st 5 innings (3-way)']


        mapper = {
            "game lines": base_market_mapper,
            "alternates": base_market_mapper,
            **{f"{irregular}": {key: f"{irregular} {value}" for key, value in base_market_mapper.items()} for irregular in irregular_ordinal_markets},
            **{f"{suffix}": {key: f"{suffix.upper()} {value}" for key, value in base_market_mapper.items()} for suffix in ordinal_suffix_markets},
        }

        return mapper.get(market_name.lower(), {}).get(odds_key, market_name)



    def convert_spread_name(self, odds_list: list[SportsbookStats], league: str):
        """Converts spread market names to the appropriate names based on the league."""
        for odds in odds_list:
            if "Spread" in odds.market and league == "MLB":
                odds.market = odds.market.replace("Spread", "Run Line")
            elif "Spread" in odds.market and league == "NHL":
                odds.market = odds.market.replace("Spread", "Puck Line")

        return odds_list


    def pph_login_helper(self, payload: dict, sportsbook_name: str, additional_headers: dict = None,
                   login_key_word_check: str = None):
        """
        Used for PPH sportsbooks that require login via ASP.NET forms.
        :param payload: The payload containing login credentials and any additional required fields.
        :param sportsbook_name: The name of the sportsbook for logging purposes.
        :param additional_headers: Any additional headers to include in the login request.
        :param login_key_word_check: A keyword to check in cookies to verify successful login.
        """
        def find_values(name):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""

        if not payload:
            raise ValueError("Payload for login cannot be empty.")

        with Session(impersonate="chrome120") as session:
            response = session.get(self.book_data.url.get("login_url"))
            soup = BeautifulSoup(response.text, "html.parser")


            starter_payload = {
                "__VIEWSTATE": find_values("__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": find_values("__EVENTVALIDATION"),
            }

            starter_payload.update(payload)

            if additional_headers:
                self.book_data.headers.update(additional_headers)

            print(starter_payload)
            response = session.post("https://bettheguys.com/Login.aspx", data=payload, headers=self.book_data.headers)

            print(response.text)

            if login_key_word_check and login_key_word_check not in session.cookies.get_dict():
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="login_failure",
                    message="Couldn't login",
                    level="error"
                )
                return None
            print(session.cookies.get_dict())
            return session.cookies.get_dict()