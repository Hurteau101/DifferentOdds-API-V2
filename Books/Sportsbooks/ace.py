import asyncio
import json
import re
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
                       'alternate runlines', 'player props']

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
                raw_league_description = league.get("Description", "").lower()
                description = raw_league_description.split(" - ")[0].lower() if "player props" in raw_league_description else raw_league_description

                found_market = any(
                    allowed_market.lower() in description
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
        utc = eastern_dt.astimezone(timezone.utc)
        return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


    def yes_no_type(self, game_data: dict, market_name: str, **kwargs) -> list:
        """
        Builds any yes/no type markets. The home team and away team indicate if its the yes/no side.
        :param game_data: The game data containing the odds information.
        :param market_name: The market name.
        """
        odds = []

        no_odds = game_data.get("hoddst") if "no" in game_data.get('htm', '').lower() else game_data.get("voddst")
        yes_odds = game_data.get("voddst") if "no" in game_data.get('htm', '').lower() else game_data.get("hoddst")

        base_mapper = kwargs.get("base_market_mapper")

        for direction, odds_value in [("under", yes_odds), ("over", no_odds)]:
            mapped_market_name = self.name_mapper(market_name=market_name, odds_key="", base_market_mapper=base_mapper)

            if not odds_value:
                continue

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=None,
                line=0.5,
                bet_type=direction,
                future=False,
                odds_format=OddsFormat(american_odds=float(odds_value)),
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

        name_mapper_func = kwargs.get("name_mapper_func")
        base_mapper = kwargs.get("base_market_mapper")

        for bet_type, line_key, odds_key in [("Over", "ovt", "ovoddst"), ("Under", "unt", "unoddst")]:
            mapped_market_name = name_mapper_func(market_name=market_name, odds_key=odds_key, base_market_mapper=base_mapper)


            total_line = game_data.get(line_key)
            total_odds = game_data.get(odds_key)
            if not total_line or not total_odds:
                continue

            raw_team_name = kwargs.get("games", {}).get("htm", '')
            market_name_split = mapped_market_name.lower().split()
            team_name = ' '.join([word for word in raw_team_name.lower().split()
                                 if word not in market_name_split and word not in ['total', 'team'] + market_name.lower().split()])

            if "team totals" in market_name.lower() or kwargs.get("player_name"):
                team_name_passed_in = kwargs.get("passed_in_team_name", None)
                team_name = team_name_passed_in if team_name_passed_in else team_name
            else:
                team_name = None

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=team_name,
                line=abs(float(total_line)),
                bet_type=bet_type,
                future=False,
                odds_format=OddsFormat(american_odds=float(total_odds)),
                bet_player=kwargs.get("player_name", None)
            ))

        return odds

    async def build_player_market(self, description_name: str, games: dict, espn_mapping: dict):
        raw_date = games.get("gmdt")
        raw_time = games.get("gmtm")
        start_date = self._build_start_date(raw_date=raw_date, raw_time=raw_time)

        league = description_name.split("-")[0].strip().lower().replace("player props", "").strip().upper()
        clean_player_market_name = re.sub(r'\s*\(.*?\)', '', games.get("gdesc", ''))

        # All markets, should have a - with the player name at index 1 and market name at index 2. If not, we don't want it.
        if " - " not in clean_player_market_name:
            return None

        player_name, raw_market_name = clean_player_market_name.split(" - ", 1)
        market_name = f"player {raw_market_name}" if not "player" in raw_market_name.lower() else raw_market_name.lower()

        found_league = espn_mapping.get(league)
        if not found_league:
            print("No league found for: ", league)
            return None

        found_team = next((
            {team_name: team_data}
            for team_name, team_data in found_league.items()
            if player_name.lower().strip() in [player.lower() for player in team_data.get("players", [])]
        ), None)

        if not found_team:
            print("No Found Team")
            return None

        found_scheduled_game_data = next((
            schedule
            for team_data in found_team.values()
            for schedule in team_data.get("schedule", [])
            if self.is_within_minutes(30, schedule.get("date"), start_date)
        ))

        if not found_scheduled_game_data:
            print("No Scheduled Game Daata")
            return None

        normalized_player_name = next((
            player
            for team_data in found_team.values()
            for player in team_data.get("players", [])
            if player.lower() == player_name.lower().strip()
        ), player_name.lower().strip())

        team_data = TeamData(
            team_a=found_scheduled_game_data.get("team"),
            team_b=found_scheduled_game_data.get("opponent")
        )

        game_data = GameData(
            start_date=start_date,
            league=league,
            team_data=team_data,
            game_key=self.generate_key([team_data.team_a, team_data.team_b, start_date]),
            odds=[]
        )

        for main_lines in games.get("GameLines", []):
            base_market_mapper = {
                "ovoddst": "Total",
                "unoddst": "Total",
            }

            game_data.odds.extend(self.total_type(games=games, game_data=main_lines, market_name=market_name.lower().strip(),
                            name_mapper_func=self.name_mapper, base_market_mapper=base_market_mapper,
                            passed_in_team_name=list(found_team.keys())[0], player_name=normalized_player_name))


        return game_data



    async def build_mainline_market(self, description_name: str, games: dict) -> GameData:
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

        game_description = (games.get("gdesc") or '').lower()

        for main_lines in games.get("GameLines", []):
            home_odds_name = "hoddst" if main_lines.get("hoddst") else "hspoddst"
            away_odds_name = "voddst" if main_lines.get("voddst") else "vspoddst"

            home_spread_odds_name = "hsprdoddst" if main_lines.get("hsprdoddst") else "hspoddst"
            home_spread_value_name = "hsprdt" if main_lines.get("hsprdt") else "hspt"
            away_spread_odds_name = "vsprdoddst" if main_lines.get("vsprdoddst") else "vspoddst"
            away_spread_value_name = "vsprdt" if main_lines.get("vsprdt") else "vspt"

            base_market_mapper = {
                home_odds_name: "Moneyline",
                away_odds_name: "Moneyline",
                home_spread_odds_name: "Spread",
                away_spread_odds_name: "Spread",
                "ovoddst": "Total",
                "unoddst": "Total",
            }

            if not any(condition in game_description for condition in special_conditions):
                game_data.odds.extend(self.moneyline_type(team_data=team_data, game_data=main_lines, market_name=modified_description,
                                                          name_mapper_func=self.name_mapper, home_odds_name=home_odds_name, away_odds_name=away_odds_name,
                                                          base_market_mapper=base_market_mapper))

                game_data.odds.extend(self.spread_type(team_data=team_data, game_data=main_lines, market_name=modified_description,
                                        name_mapper_func=self.name_mapper, home_spread_odds_name=home_spread_odds_name,
                                        away_spread_odds_name=away_spread_odds_name, home_spread_value_name=home_spread_value_name,
                                        away_spread_value_name=away_spread_value_name, base_market_mapper=base_market_mapper, league=league))

                game_data.odds.extend(self.total_type(games=games, game_data=main_lines, market_name=modified_description,
                                                      name_mapper_func=self.name_mapper, base_market_mapper=base_market_mapper))
            else:
                game_data.odds.extend(self.yes_no_type(game_data=main_lines, market_name=modified_description, base_market_mapper=base_market_mapper))


        return game_data


    async def run_book(self):
        cookies = await self.load_cookies()
        if not cookies:
            return

        async with aiohttp.ClientSession(cookies=cookies) as session:
            espn_redis = RedisAsyncManager(database=8)
            espn_mapping = await espn_redis.get_data("espn_mapping")

            raw_leagues = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("leagues_url"),
                method="GET",
                headers=self.book_data.headers,
            )

            leagues = self.build_league_ids(raw_leagues, exclude_player_props=False)

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

            # mainlines = {}
            # props = {}
            events = {}

            for market in league_list:
                description_name = market.get("Description", "")
                is_player_prop = True if "player prop" in description_name.lower() else False

                for games in market.get("Games", []):
                    if not games:
                        continue

                    if not is_player_prop:
                        markets = await self.build_mainline_market(description_name=description_name, games=games)
                    else:
                        markets = await self.build_player_market(description_name=description_name, games=games, espn_mapping=espn_mapping)

                    if markets:
                        self.add_to_events(events, markets, GameData)



            betvegas_data = list(events.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=betvegas_data)

            final_mapping = {}

            # Loop through it again, due to player props already being mapped, but mainline props aren't.
            # So then there are numerous duplicated dictionaries. This is because the book doesn't use the proper
            # spelling when creating the event, so this causes BOS Celtivs vs TOR Raptors, until its ran through
            # map_runner where its properly mapped, but then the player mapping isn't already properly mapped, so you end
            # up with similar events that should be grouped together.
            for mapped in mapped_data:
                self.add_to_events(final_mapping, mapped, GameData)

            final_data = list(final_mapping.values())

            await self.store_data(
                database=self.redis_database,
                data_to_store=final_data,
                book_name=self.book_data.name
            )

            return final_data


if __name__ == "__main__":
    ace = Ace()
    asyncio.run(ace.run_book())