import os
from itertools import chain

import aiohttp
import requests
from dotenv import load_dotenv

from Settings.pph_base import SportsbookBase
from Settings.book_base import SportbookRequestType
import asyncio
from bs4 import BeautifulSoup
import dotenv

class Aces(SportsbookBase):
    MAPPER = {
        "game": "full",
        "first quarter": "1Q",
    }
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="aces")

    def _login(self):
        def find_values(name):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""

        login_url = self.book_data.url["login_url"]
        session = requests.Session()
        request_session = session.get(login_url)
        soup = BeautifulSoup(request_session.text, "html.parser")

        load_dotenv()

        payload = {
            "__VIEWSTATE": find_values("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR"),
            "Account": os.getenv("ACES_USERNAME"),
            "Password": os.getenv("ACES_PASSWORD"),
            "BtnSubmit": "Sign in"
        }

        web_session = session.post(login_url, data=payload, headers=self.book_data.headers)

        if "Please sign in" in web_session.text:
            self.file_logger.log(
                sportsbook="aces",
                message="Login failed for Ace Sportsbook."
            )
            return None

        return session.cookies.get_dict()

    async def extract_leagues(self, session):
        raw_league_data = await self.api_caller(
            session=session,
            url=self.book_data.url["league_list_url"],
            headers=self.book_data.headers,
            method=self.book_data.method
        )

        league_data = self.check_api_response(sportsbook="aces", results=raw_league_data)
        if not league_data:
            return

        return [
            {
                "league_name": result.get("IndexName"),
                "league_id": result.get("IdLeague")
            }

            for result in league_data.get("result", [])
        ]


    def _extract_game_data(self, game_data):
        # vsprdh = Visitor Team Spread
        # hsprdh = Home Team Spread
        # voddsh - Moneyline Visitor
        # hoddsh - Moneyline Home
        # idgm - Game ID --- USE THIS TO PREVENT DUPLICATES


        # htm - Stat Type

        stat_type = game_data.get("gpd")
        game_date = game_data.get("gmdt")
        period = game_data.get("GAME")



    async def run_book(self):
        cookies = self._login()
        if not cookies:
            return

        async with aiohttp.ClientSession(cookies=cookies) as session:
            leagues = await self.extract_leagues(session)
            if not leagues:
                return

            # tasks = [
            #     self.api_caller(
            #         session=session,
            #         url=self.book_data.url["games_url"].format(league_id=league["league_id"]),
            #         headers=self.book_data.headers,
            #         method=self.book_data.method,
            #         parse_json=True
            #     )
            #     for league in leagues[:2]
            # ]

            # results = await asyncio.gather(*tasks)

            results = await self.api_caller(
                session=session,
                url=self.book_data.url["games_url"].format(league_id=3771),
                headers=self.book_data.headers,
                method=self.book_data.method,
                parse_json=True
            )

            # with open("aces_league_3771.json", "w") as f:
            #     import json
            #     json.dump(results, f, indent=2)

            leagues = results.get("result", {}).get("listLeagues", [])

            games = chain.from_iterable(
                league.get("Games", [])
                for league_group in leagues
                for league in league_group
            )

            children = chain.from_iterable(game.get("GameChilds", []) for game in games)
            gamelines = chain.from_iterable(child.get("GameLines", []) for child in children)

            for line in gamelines:
                print(line)

            # extracted_data = self._extract_game_data(data)

            # for index, result in enumerate(results):
            #     print("hit")
            #     game_data = result.get("result", {}).get("listLeagues", [])
            #     with open(f"aces_league_{leagues[index]['league_name']}.json", "w") as f:
            #         import json
            #         json.dump(game_data, f, indent=2)










if __name__ == "__main__":
    aces = Aces()
    asyncio.run(aces.run_book())