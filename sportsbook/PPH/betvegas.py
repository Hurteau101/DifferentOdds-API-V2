import os
import asyncio
from collections import defaultdict

import aiohttp
import requests
from Settings.book_base import SportbookRequestType
from Settings.pph_model import GameData, TeamData, Markets
from Settings.pph_base import SportsbookBase
from sportsbook.PPH.pph_mapper import BETVEGAS_LEAGUE_MAPPER

class BetVegas(SportsbookBase):
    AVOID_MARKETS = ["NHL - GRAND SALAMI"]

    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="1bv")
        self.app_token = os.getenv("BETVEGAS_APP_TOKEN")

    def _pph_login(self, *args, **kwargs):
        session = requests.Session()
        data = {
            "UserName": os.getenv("BETVEGAS_USERNAME"),
            "Password": os.getenv("BETVEGAS_PASSWORD"),
        }

        headers = {
            'Referer': 'https://everygame247.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            **self.book_data.headers
        }


        session.post(url=self.book_data.url.get("login_url"), data=data, headers=headers)

        return session.cookies.get_dict()

    async def _get_player_token(self, session):
        player_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("player_token_url"),
            headers={
                "Referer": "https://everygame247.com/BetSlip/",
                **self.book_data.headers,
            },
            params={
                "player": os.getenv("BETVEGAS_USERNAME"),
                "password": os.getenv("BETVEGAS_PASSWORD"),
                "domain": "https://everygame247.com"
            },
            method="POST"
        )

        return player_data.get("PlayerToken")


    def _extract_markets(self, game_data, league, league_id, raw_league):
        away_team = game_data.get("VISITOR_TEAM")
        home_team = game_data.get("HOME_TEAM")
        game_date = self.cache_time(game_data.get("DATE_TIME_GAME"))
        markets = []

        market_mapper = {
            "moneyline": "Moneyline",
            "spread": "Spread",
            "total": "Total"
        }

        if "NO OVERTIME" in raw_league:
            market_mapper.update({
                "moneyline": "Moneyline (Regulation)",
                "spread": "Spread (Regulation)",
                "total": "Total (Regulation)"
            })

            away_team = away_team.replace(" (NO OT)", "")
            home_team = home_team.replace(" (NO OT)", "")


        team_key = self._generate_key([home_team, away_team, game_date])

        moneyline_map = [
            (market_mapper.get("moneyline"), "HOME_ODDS", home_team),
            (market_mapper.get("moneyline"), "VISITOR_ODDS", away_team)
        ]


        total_map = [
            (market_mapper.get("total"), "OVER_ODDS", "over", "TOTAL_OVER"),
            (market_mapper.get("total"), "UNDER_ODDS", "under", "TOTAL_UNDER")
        ]

        spread_map = [
            (market_mapper.get("spread"), home_team, "HOME_SPREAD_ODDS", "HOME_SPREAD"),
            (market_mapper.get("spread"), away_team, "VISITOR_SPREAD_ODDS", "VISITOR_SPREAD")
        ]

        for market, odds_key, team in moneyline_map:
            american_odds = game_data.get(odds_key)
            if american_odds:
                markets.append(Markets(
                    market=market,
                    american_odds=game_data.get(odds_key),
                    bet_team=team,
                    bet_type=None,
                    line=None,
                    bet_player=None
                ))

        for market, odds_key, bet_type, line_key in total_map:
            american_odds = game_data.get(odds_key)
            if american_odds:
                markets.append(Markets(
                    market=market,
                    american_odds=game_data.get(odds_key),
                    bet_team=None,
                    bet_type=bet_type,
                    line=game_data.get(line_key),
                    bet_player=None
                ))

        for market, team_name, odds_key, line_key in spread_map:
            american_odds = game_data.get(odds_key)
            if american_odds:
                markets.append(Markets(
                    market=market,
                    american_odds=game_data.get(odds_key),
                    bet_team=team_name,
                    bet_type=None,
                    line=game_data.get(line_key),
                    bet_player=None
                ))

        if not markets:
            return None

        return GameData(
            book_name="1bv",
            start_date=self.cache_time(game_data.get("DATE_TIME_GAME")),
            league=league,
            event_name=f"{home_team} vs. {away_team}",
            team_data=TeamData(
                team_a=home_team,
                team_b=away_team,
                team_key=team_key
            ),
            league_id=league_id,
            raw_league_name=raw_league,
            odds=markets,
        )


    async def run_book(self):
        cookies = self._pph_login()

        async with aiohttp.ClientSession(cookies=cookies, headers=self.book_data.headers) as session:
            player_token = await self._get_player_token(session=session)
            if not player_token:
                return

            league_ids = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_list_url"),
                headers={
                    "playerToken": player_token,
                    **self.book_data.headers,
                },
            )

            league_ids = [
                {
                    "league_name": BETVEGAS_LEAGUE_MAPPER.get(league_info.get("LeagueDescription").lower(), league_info.get("LeagueDescription").upper()),
                    "league_id": league_info.get("LeagueId"),
                    "raw_league": league_info.get("LeagueDescription")
                }

                for league in league_ids.get("Groups")
                for league_info in league.get("Leagues", [])
                if league_info.get("LeagueDescription") not in self.AVOID_MARKETS
            ]

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("game_markets"),
                    headers={
                        "playerToken": player_token,
                        **self.book_data.headers,
                    },
                    params={
                        "leagueId": league.get("league_id"),
                        "loadAgentLines": "true",
                        "loadDefaultOdds": "true",
                        "sportId": league.get("league_name"),
                        "loadPropsEvents": "true"
                    }
                )

                for league in league_ids
            ]

            results = await asyncio.gather(*tasks)

            game_data = []

            for league, result in zip(league_ids, results):
                league_id = league.get("league_id")
                raw_league = league.get("raw_league")

                for league_result in result.get("Events", {}).get("LEAGUES", []):
                    for game_info in league_result.get("EVENTS", []):
                        games = self._extract_markets(game_info, league.get("league_name"), league_id, raw_league)
                        if games:
                            game_data.append(games)


            serialize = self.serialize_data(game_data)
            self.create_json(serialize, "1bv.json")


if __name__ == "__main__":
    betvegas = BetVegas()
    asyncio.run(betvegas.run_book())




