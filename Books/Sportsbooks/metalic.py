import asyncio
import os
import re
from itertools import chain

import aiohttp
from dotenv import load_dotenv
from multidict import CIMultiDictProxy
from trio import Semaphore

from Books.Bases.pph_base import PPHBookBase
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.request_caller import SportbookRequestType

load_dotenv()

class Metallic(PPHBookBase):
    VALID_LEAGUES = ["NBA", "MLB", "NHL", "NFL", "CBB", "CFB", "NCAA BASKETBALL", "WNCAA BASKETBALL"]

    REMOVED_MARKETS = ["player", "futures", "live", "props"]

    INTERNAL_LEAGUE_MAPPER = {
        "ncaa basketball": "NCAAB",
        "wncaa basketball": "NCAAW",
    }

    KEY_CONVENTION = {
        "s": "Spread",
        "m": "Moneyline",
        "t": "Total",
        "to": "Team Total - Over",
        "tu": "Team Total - Under"
    }


    def __init__(self):
        super().__init__(book_name="metallic", request_type=SportbookRequestType.ASYNC)

    async def load_auth(self) -> str | None:
        """Extracts the cookies from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("metallic_token")


    def build_league_ids(self, raw_leagues: dict, league_filter: bool = True, filter_markets: bool = True) -> dict:
        """Build a mapping of league IDs to their corresponding league names and sport types."""
        league_ids = {}

        for league_name, league_data in raw_leagues.get("Items", {}).items():
            if league_filter and league_name.upper() not in self.VALID_LEAGUES:
                continue

            for item in league_data.get("items", []):

                if filter_markets and any(market in item.get("SportSubType", '').lower() for market in self.REMOVED_MARKETS):
                    continue

                for combine in item.get("CombinedItems", []):
                    league_ids.setdefault(combine.get("IdSportType"), [])
                    league_ids[combine.get("IdSportType")].append({
                        "league": league_name,
                        "sport_type": item.get("SportType"),
                        "period": item.get("PeriodDescription"),
                        "sport_id": combine.get("IdSportType"),
                        "period_numer": combine.get("PeriodNumber"),
                        "sport_subtype": item.get("SportSubType")
                    })

        return league_ids

    def extract_teams(self, team_list: list) -> TeamData | None:
        """Extract Team Data"""
        if len(team_list) != 2:
            return None

        raw_team_a, raw_team_b = (team.get("n", "") for team in team_list)

        team_a, team_b = (re.sub(r'\s*.{3}#.*', '', team) for team in [raw_team_a, raw_team_b])

        return TeamData(team_a=team_a, team_b=team_b)

    def _moneyline_type(self, market_name: str, market_data: dict, **kwargs) -> SportsbookStats:
        return SportsbookStats(
            market=market_name,
            bet_team=kwargs.get("team", None),
            line=None,
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=market_data.get("o"))
        )

    def _spread_type(self, market_name: str, market_data: dict, **kwargs) -> SportsbookStats:
        return SportsbookStats(
            market=market_name,
            bet_team=kwargs.get("team", None),
            line=market_data.get("p", None),
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=market_data.get("o"))
        )

    def _total_type(self, market_name: str, market_data: dict, **kwargs) -> SportsbookStats:
        if "- over" in market_name.lower() or "- under" in market_name.lower():
            bet_type = market_name.split("-")[-1].strip().lower()
            market_name = market_name.split("-")[0].strip()
        else:
            bet_type = "over" if kwargs.get("index", '') == 0 else "under"


        return SportsbookStats(
            market=market_name,
            bet_team=kwargs.get("team", None) if "team" in market_name.lower() else None,
            line=market_data.get("p", None),
            bet_type=bet_type,
            future=False,
            odds_format=OddsFormat(american_odds=market_data.get("o"))
        )

    def market_controller(self, mapped_market_name: str, market_name: str, market_data: dict, team: str, **kwargs) -> SportsbookStats | None:
        """
        Controller function to determine which market builder to use based on the mapped market name.
        These functions use the _ convention as we don't want to inherit/override the base functions (money_type, spread_type, etc), that are similar on other PPHs.
        """
        mapper = {
            "moneyline": self._moneyline_type,
            "spread": self._spread_type,
            "total": self._total_type,
            "team total - over": self._total_type,
            "team total - under": self._total_type,
        }

        handler = mapper.get(mapped_market_name.lower())

        if not handler:
            return None

        return handler(market_name=market_name, market_data=market_data, team=team, **kwargs)


    def build_markets(self, event_data: dict, league_dict: dict) -> list:
        sport_id = event_data.get("sc", {}).get("spid", -1)
        period_id = event_data.get("sc", {}).get("p", -1)
        sport_subtype = event_data.get("sc", {}).get("l", "")

        found_sport_id = league_dict.get(sport_id, [])

        found_league_dict = next((
            league
            for league in found_sport_id
            if all([
                league.get("period_numer") == period_id,
                league.get("sport_subtype", '').lower() == sport_subtype.lower()
            ])
        ), None)

        if not found_league_dict:
            return None

        game_data = []

        for schedule in event_data.get("sc", {}).get("schl", []):
            if schedule.get("l", '').lower() in ["player props"]:
                continue

            for game in schedule.get("g", []):
                # Filter out any live games, unplayable markets, etc.
                if any([game.get("ob", False), game.get("il", False), game.get("ip", False), "disclaimer" in game.get('l', '').lower()]):
                    continue

                game_date = game.get("to", "")

                team_list = game.get("ts", [])
                team_data = self.extract_teams(team_list=team_list)

                if not team_data:
                    return None

                game_key = self.generate_key([team_data.team_a, team_data.team_b, game_date])

                game = GameData(
                    start_date=game_date,
                    league=self.INTERNAL_LEAGUE_MAPPER.get(found_league_dict.get("league").lower(), found_league_dict.get("league")),
                    team_data=team_data,
                    odds=[],
                    game_key=game_key
                )

                # Enumerate, as first index in the list is over [index: 0], whereas the second is under [index: 1].
                for index, items in enumerate(team_list):

                    team = re.sub(r'\s*.{3}#.*', '', items.get("n", '').lower())

                    for market_indicator, market_data in items.get("ls", {}).items():
                        period = event_data.get("sc", {}).get("pd", '').lower().replace("game", "").strip()

                        mapped_market_name = self.KEY_CONVENTION.get(market_indicator.lower(), market_indicator)
                        market_name = mapped_market_name if not period else f"{period} {mapped_market_name}"


                        for market in market_data:
                            odds = self.market_controller(market_name=market_name, market_data=market,
                                                          mapped_market_name=mapped_market_name, team=team, index=index)
                            if odds:
                                game.odds.append(odds)

                if game.odds:
                    game_data.append(game)

        return game_data


    async def call_with_limit(self, sport_id, league_data, semaphore: Semaphore, session: aiohttp.ClientSession, auth_token: str):
        """Helper function to call the API with a semaphore limit."""
        async with semaphore:
            # await asyncio.sleep(0.5)
            return await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("market_url"),
                method=self.book_data.method,
                headers={
                    **self.book_data.headers,
                    "Authorization": f"Bearer {auth_token}"
                },
                payload=[{"IdSport": sport_id, "Period": league_data.get("period_numer", -1)}],
            )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            auth_token = await self.load_auth()

            if not auth_token:
                return

            raw_leagues = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_url"),
                method="GET",
                headers={
                    **self.book_data.headers,
                    "Authorization": f"Bearer {auth_token}"
                }
            )

            league_ids = self.build_league_ids(raw_leagues)

            # Use semapmore, as there is rate limits.
            semaphore = asyncio.Semaphore(3)

            tasks = await asyncio.gather(
                *[self.call_with_limit(sport_id=sport_id, league_data=league_data, semaphore=semaphore,
                                       auth_token=auth_token, session=session)
                  for sport_id, league_details in league_ids.items()
                  for league_data in league_details

                  ]
            )

            if not tasks:
                print("No Tasks")
                return

            # Flatten list a bit.
            events = list(chain.from_iterable(
                item
                for item in tasks
                if item
            ))

            event_data = {}

            for event in events:
                game_data = self.build_markets(event_data=event, league_dict=league_ids)
                if not game_data:
                    continue

                for game in game_data:
                    self.add_to_events(event_data, game, GameData)


            metalic_data = list(event_data.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=metalic_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data





if __name__ == "__main__":
    metallic = Metallic()
    asyncio.run(metallic.run_book())