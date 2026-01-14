import json
from abc import ABC

import aiohttp.client
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from Mapper.mapper import Mapper
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.Mixin.mixins import ApiResponseMixin
from Settings.Sportsbook_Settings.sportsbook_book_base import SportsbookBase

from Settings.sportsbook_config import SportsbookConfig


class PPHBookBase(SportsbookBase):
    def __init__(self, request_type, sportsbook_name: str, log_directory="Sportsbook Logs", log_name=None):
        self.book_data = SportsbookConfig.get_pph_provider(sportsbook_name)
        super().__init__(request_type, log_directory=log_directory, log_name=log_name, sportsbook_name=sportsbook_name)
        load_dotenv()
        self.mapper = Mapper()
        self.LEAGUE_MAPPING = LEAGUES
        self.STAT_TYPES = STAT_TYPES

    @staticmethod
    def parser(text_data: str, key_name: str = None, is_inner: bool = False) -> dict:
        """
        Parser to help reformat a text block into JSON format.
        :param key_name: The key name to use for the parsed data.
        :param text_data: The raw text data to parse.
        :param is_inner: Whether to parse inner JSON data.
        """
        if is_inner and not key_name:
            raise ValueError("Key name must be provided for parsing.")

        outer = json.loads(text_data)

        if is_inner:
            inner = json.loads(outer[key_name])
            return inner

        return outer

    def check_api_response(self, sportsbook: str, results: list):
        return ApiResponseMixin.check_api_response(self, sportsbook, results)

    async def api_caller(
            self,
            session,
            url,
            headers,
            payload=None,
            data=None,
            params=None,
            method="GET",
            use_parser=False,
            key_name=None,
            is_inner=False
    ):
        if use_parser and key_name is None:
            raise ValueError("key_name must be provided when use_parser is True.")

        request_args = {}

        if payload is not None:
            request_args["json"] = payload

        if data is not None:
            request_args["data"] = data

        if params is not None:
            request_args["params"] = params

        method = method.upper()
        if method == "POST":
            request = session.post
        else:
            request = session.get

        async with request(url, headers=headers, **request_args) as response:
            if response.status != 200:
                return None

            try:
                if use_parser:
                    data = await response.text()
                    return self.parser(data, key_name=key_name, is_inner=is_inner)

                return await response.json()
            except aiohttp.client.ContentTypeError:
                data = await response.text()
                if use_parser:
                    return self.parser(data, key_name=key_name, is_inner=is_inner)

                return json.loads(data)

    def _pph_login(self, payload: dict, sportsbook_name: str, additional_headers: dict = None,
                   login_key_word_check: str = None):
        """
        Used for PPH sportsbooks that require login via ASP.NET forms.
        :param payload: The payload containing login credentials and any additional required fields.
        :param sportsbook_name: The name of the sportsbook for logging purposes.
        :param additional_headers: Any additional headers to include in the login request.
        :param login_key_word_check: A keyword to check in cookies to verify successful login.
        """

        if not payload:
            raise ValueError("Payload for login cannot be empty.")

        login_url = self.book_data.url.get("login_url")
        session = requests.Session()
        request_session = session.get(login_url)
        soup = BeautifulSoup(request_session.text, "html.parser")

        def find_values(name):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""

        starter_payload = {
            "__VIEWSTATE": find_values("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": find_values("__EVENTVALIDATION"),
        }

        starter_payload.update(payload)

        if additional_headers:
            self.book_data.headers.update(additional_headers)

        session.post(login_url, data=payload, headers=self.book_data.headers)

        if login_key_word_check and login_key_word_check not in session.cookies.get_dict():
            self.file_logger.log(
                sportsbook=sportsbook_name,
                message=f"Login failed for {sportsbook_name} Sportsbook."
            )
            return None

        return session.cookies.get_dict()

    def _unique_teams(self, sportsbook_data: list, sportsbook):
        team_set = set()
        team_data = []

        for data in sportsbook_data:
            if not data.solo_game:
                league = data.league
                team_a = data.team_data.team_a
                team_b = data.team_data.team_b

                for team in (team_a, team_b):
                    key = (team, league)
                    if key not in team_set:
                        team_set.add(key)
                        team_data.append({
                            "team_name": team.strip(),
                            "league": league,
                            "solo_game": data.solo_game,
                            "sportsbook": sportsbook
                        })

        return team_data

    # REFORMAT CODE LATER SINCE IT IS SIMILAR TO DFSBOOKBASE _database_mapper
    async def _database_mapper(self, sportsbook_data: list):
        sportsbook = self.__class__.__name__
        unique_data = self._unique_teams(sportsbook_data=sportsbook_data, sportsbook=sportsbook)
        mapped_teams = await self.mapper.controller(unique_data)
        team_lookup = {
            f'{team["original_name"].lower()}-{team["league"]}': team
            for team in mapped_teams
        }

        for data in sportsbook_data:
            # print(data)
            # if data.future is not None and data.future:
            #     continue

            for side in ['team_a', 'team_b']:
                league = data.league
                team_name_attr = getattr(data.team_data, side)
                if not team_name_attr:
                    continue

                team_key = f"{team_name_attr.lower()}-{league}"
                team = team_lookup.get(team_key)
                if team:
                    data.league = team["league"]
                    setattr(data.team_data, side, team["team_name"])
                    setattr(data.team_data, f"{side}_abbreviation", team.get("abbreviation"))

        return sportsbook_data


    def formatter(self, data):
        games = {}

        for entry in data:
            team_data = entry.team_data
            game_key = team_data.team_key

            games[game_key] = {
                "league": entry.league,
                "start_date": entry.start_date,
                "teams": [
                    {
                        "team_a": entry.team_data.team_a,
                        "team_a_abbreviation": entry.team_data.team_a_abbreviation,
                        "team_b": entry.team_data.team_b,
                        "team_b_abbreviation": entry.team_data.team_b_abbreviation,
                    }
                ],
                "solo_game": entry.solo_game,
                "future": entry.future,
            }

            for odds in entry.odds:
                odds_data = {
                    "market": odds.market,
                    "american_odds": odds.american_odds,
                    "bet_team": odds.bet_team,
                    "bet_type": odds.bet_type,
                    "line": odds.line,
                    "bet_player": odds.bet_player,
                }

                games[game_key].setdefault("odds", []).append(odds_data)

        return games


