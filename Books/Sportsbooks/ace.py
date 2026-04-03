import asyncio
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiohttp
from Books.Bases.pph_base import PPHBookBase
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import TeamData, GameData, OddsFormat, get_static_mapping
from Settings.Models.sportsbooks_models import SportsbookStats
from Utils.request_caller import SportbookRequestType
from itertools import chain


## GAME LINES - Moneyline, Total, Spreads
class Ace(PPHBookBase):
    VALID_LEAGUES = ["NBA", "MLB", "NHL", "NFL", "CBB", "CFB"]

    # Allowed markets refer to the different sections on ace.
    ALLOWED_MARKETS = ["game lines", 'period lines', 'alternative lines', 'team totals', '1h', 'innings', '1st 5', '1st inning',
                       'alternate runlines']

    # Some ALLOWED_MARKETS will have multiple markets, so we have to remove any we don't want.
    SPECIAL_REMOVED_MARKETS = ['3 way', 'hits']

    # Stop words are words we want to check the description name against, and remove if they are in the description,
    # for mapping purposes - Also have to include known leagues, since sometimes the leagues are random non league
    # identifiers like MLB is 'soc'.
    STOP_WORDS = ['basketball', 'college', 'hockey', 'baseball', 'football', 'nhl', 'nba', 'mlb', 'nfl', 'cbb', 'cfb']


    def __init__(self):
        super().__init__(book_name="ace", request_type=SportbookRequestType.ASYNC)

        # Contains the proper team names, as game lines section is the only section
        # that will have the proper team names, so we want to store here, so they can be referenced for the other sections,
        # that don't have the proper team names.
        self.league_dict = {}

        self.stat_mapping = get_static_mapping().get("stats", {})


    async def load_cookies(self) -> dict | None:
        """Extracts the cookies from Redis."""
        redis_instance = RedisAsyncManager(database=5)
        return await redis_instance.get_data("ace_cookies")

    def build_league_ids(self, raw_leagues: dict, exclude_player_props: bool = True, league_filter: bool = True,
                         filter_markets: bool = True, excluded_markets: bool = True) -> dict:
        """Extracts the league ids and associates it with the league name, but only for the leagues we care about"""
        league_ids = {}

        for league in raw_leagues.get("result", []):
            league_name = league.get("IndexName")

            if league_filter and league_name not in self.VALID_LEAGUES:
                continue

            if exclude_player_props and league.get("IdSport", '').lower() == "prop":
                continue

            if filter_markets:
                found_market = any(
                    allowed_market.lower() in league.get("Description", "").lower()
                    for allowed_market in self.ALLOWED_MARKETS
                )

                if not found_market:
                    continue

            if excluded_markets:
                found_inner_market = any(
                    inner_market.lower() in league.get("Description", "").lower().replace("-", " ")
                    for inner_market in self.SPECIAL_REMOVED_MARKETS
                )

                if found_inner_market:
                    continue


            league_ids[league["IdLeague"]] = league_name

        return league_ids

    async def view_league_markets(self, raw_leagues: dict, session: aiohttp.ClientSession):
        """Builds a JSON file, with the market name, and the league"""
        leagues = self.build_league_ids(raw_leagues, league_filter=True, exclude_player_props=True, filter_markets=True)
        league_ids = ",".join(str(league_id) for league_id in leagues.keys())
        markets = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("market_url"),
            method="GET",
            headers=self.book_data.headers,
            params={
                "WT": 0,
                "lg": league_ids
            }
        )

        market_data = {
            league.get("IdLeague"): league.get("Description")
            for market in markets.get("result", {}).get("listLeagues", [])
            for league in market
        }

        with open("ace_filtered_market_viewer_NEW.json", "w") as f:
            json.dump(market_data, f, indent=2)


    def _build_start_date(self, raw_date: str, raw_time: str) -> str | None:
        """Builds the start date for the game, converting from the raw date and time format provided by the API to a datetime object in UTC timezone."""
        if not raw_date or not raw_time:
            return None

        year = raw_date[:4]
        month = raw_date[4:6]
        day = raw_date[6:8]

        raw_date_string = f"{year}-{month}-{day} {raw_time}"
        game_date_dt = datetime.strptime(raw_date_string, "%Y-%m-%d %H:%M:%S")
        eastern_dt = game_date_dt.replace(tzinfo=ZoneInfo("America/New_York"))
        return eastern_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


    def name_mapper(self, description_name: str, odds_key: str) -> str:
        """Maps the description name and odds key to a market name"""
        ordinal_suffix_markets = ["1h", "2h", "1p", "2p", "3p", '1q', '2q', '3q', '4q']

        irregular_ordinal_markets = ["3p regulation", '3rd innings', '7th inning', '1st 5 innings', '1st 5 innings (3-way)']

        regular_markets = {
            "hoddst": "Moneyline",
            "voddst": "Moneyline",
            "hsprdoddst": "Spread",
            "vsprdoddst": "Spread",
            "ovoddst": "Total",
            "unoddst": "Total",
        }

        mapper = {
            "game lines": regular_markets,
            "alternates": regular_markets,
            **{f"{irregular}": {key: f"{irregular} {value}" for key, value in regular_markets.items()} for irregular in irregular_ordinal_markets},
            **{f"{suffix}": {key: f"{suffix.upper()} {value}" for key, value in regular_markets.items()} for suffix in ordinal_suffix_markets},
        }

        return mapper.get(description_name.lower(), {}).get(odds_key, description_name)


    def moneyline_type(self, team_data: TeamData, game: dict, modified_description: str) -> list:
        """Builds any moneyline type markets, as the description names have the same odds keys, just different description names,
        so we can use the same function for all of them.
        :param team_data: The team data for the game, containing the team names.
        :param game: The game data containing the odds information.
        :param modified_description: The modified description name.
        """
        odds = []

        for team, odds_key in [(team_data.team_a, "hoddst"), (team_data.team_b, "voddst")]:
            market_name = self.name_mapper(description_name=modified_description, odds_key=odds_key)

            moneyline_odds = game.get(odds_key)
            if not moneyline_odds:
                continue

            odds.append(SportsbookStats(
                market=market_name,
                bet_team=team,
                line=None,
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(moneyline_odds)),
            ))

        return odds

    def yes_no_type(self, game: dict, modified_description: str) -> list:
        """
        Builds any yes/no type markets. The home team and away team indicate if its the yes/no side.
        :param game: The game data containing the odds information.
        :param description_name: The original description name of the market.
        """
        odds = []

        no_odds = game.get("hoddst") if "no" in game.get('htm', '').lower() else game.get("voddst")
        yes_odds = game.get("voddst") if "no" in game.get('htm', '').lower() else game.get("hoddst")

        for direction, odds_value in [("under", yes_odds), ("over", no_odds)]:
            market_name = self.name_mapper(description_name=modified_description, odds_key="")

            odds.append(SportsbookStats(
                market=market_name,
                bet_team=None,
                line=0.5,
                bet_type=direction,
                future=False,
                odds_format=OddsFormat(american_odds=float(odds_value)),
            ))

        return odds


    def spread_type(self, team_data: TeamData, game: dict, modified_description: str) -> list:
        """Builds any spread type markets, as the description names have the same odds keys, just different description names
        :param team_data: The team data for the game, containing the team names.
        :param game: The game data containing the odds information.
        :param modified_description: The modified description name.
        """
        odds = []

        for team, line_key, odds_key in [(team_data.team_a, "hsprdt", "hsprdoddst"), (team_data.team_b, "vsprdt", "vsprdoddst")]:
            market_name = self.name_mapper(description_name=modified_description, odds_key=odds_key)

            spread_odds = game.get(odds_key)
            spread_line = game.get(line_key)

            if not spread_odds or spread_line is None:
                continue

            odds.append(SportsbookStats(
                market=market_name,
                bet_team=team,
                line=float(spread_line),
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(spread_odds)),
            ))

        return odds

    def total_type(self, games: dict, game: dict, modified_description: str) -> list:
        """Builds any total type markets, as the description names have the same odds keys, just different description names
        :param games: The outer game data container that contains the team names, as the game dict doesn't contain this information.
        :param game: The game data containing the odds information.
        :param modified_description: The modified description name.
        """
        odds = []

        for bet_type, line_key, odds_key in [("Over", "ovt", "ovoddst"), ("Under", "unt", "unoddst")]:
            market_name = self.name_mapper(description_name=modified_description, odds_key=odds_key)

            total_line = game.get(line_key)
            total_odds = game.get(odds_key)
            if not total_line or not total_odds:
                continue

            raw_team_name = games.get("htm", '')
            market_name_split = market_name.lower().split()
            team_name = ' '.join([word for word in raw_team_name.lower().split()
                                 if word not in market_name_split and word not in ['total', 'team', market_name.lower().split()]])


            odds.append(SportsbookStats(
                market=market_name,
                bet_team=team_name if "team totals" in market_name.lower() else None,
                line=abs(float(total_line)),
                bet_type=bet_type,
                future=False,
                odds_format=OddsFormat(american_odds=float(total_odds)),
            ))

        return odds



    async def build_market(self, description_name: str, games: dict) -> GameData:
        """Builds the markets
        :param description_name: The description name of the section
        :param games: The game data dict
        """
        raw_date = games.get("gmdt")
        raw_time = games.get("gmtm")
        start_date = self._build_start_date(raw_date=raw_date, raw_time=raw_time)

        group_id = games.get("idgp","")
        league = games.get("idspt", "")

        # Store these ideas for future markets, as we can get the proper team names.
        if group_id and "game lines" in description_name.lower():
            self.league_dict[group_id] = {
                "home": games.get("htm"),
                "away": games.get("vtm")
            }


        team_data = TeamData(
            team_a=self.league_dict.get(group_id, {}).get("home") if group_id else games.get("htm"),
            team_b=self.league_dict.get(group_id, {}).get("away") if group_id else games.get("vtm")
        )

        game_key = self.generate_key([team_data.team_a, team_data.team_b, start_date])

        game_data = GameData(
            start_date=start_date,
            league=league,
            team_data=team_data,
            odds=[],
            game_key=game_key
        )

        stopwords = [
            team_data.team_a.lower() if team_data.team_a else "",
            team_data.team_b.lower() if team_data.team_b else "",
            league.lower() if league else "",
            "-",
        ] + self.STOP_WORDS

        modified_description_list = [
            word for word in description_name.lower().split()
            if word.lower() not in stopwords
        ]

        raw_modified_description = " ".join(modified_description_list).strip()
        modified_description = self.stat_mapping.get(raw_modified_description, raw_modified_description)


        special_conditions = ['yes/no']
        game_description = games.get("gdesc", '').lower()


        for main_lines in games.get("GameLines", []):
            if not any(condition in game_description for condition in special_conditions):
                game_data.odds.extend(self.moneyline_type(team_data=team_data, game=main_lines, modified_description=modified_description))
                game_data.odds.extend(self.spread_type(team_data=team_data, game=main_lines, modified_description=modified_description))
                game_data.odds.extend(self.total_type(games=games, game=main_lines, modified_description=modified_description))
            else:
                game_data.odds.extend(self.yes_no_type(game=main_lines, modified_description=modified_description))


        return game_data


    async def run_book(self):
        cookies = await self.load_cookies()
        if not cookies:
            return

        async with aiohttp.ClientSession(cookies=cookies) as session:
            raw_leagues = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("leagues_url"),
                method="GET",
                headers=self.book_data.headers
            )

            leagues = self.build_league_ids(raw_leagues)

            markets = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("market_url"),
                method="GET",
                headers=self.book_data.headers,
                params={
                    "WT": 0,
                    "lg": ",".join(str(league_id) for league_id in leagues.keys())
                }
            )

            if not markets:
                return

            league_list = chain.from_iterable(markets.get("result", {}).get("listLeagues", []))

            events = {}
            for market in league_list:
                description_name = market.get("Description", "")

                for games in market.get("Games", []):
                    markets = await self.build_market(description_name=description_name, games=games)

                    if markets:
                        self.add_to_events(events, markets, GameData)

            betvegas_data = list(events.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=betvegas_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data


if __name__ == "__main__":
    betvegas = BetVegas()
    asyncio.run(betvegas.run_book())