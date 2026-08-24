import os
import re
from itertools import chain
import pytz
from rapidfuzz import process, fuzz
from datetime import datetime, timezone
from Books.Bases.pph_base import PPHBookBase
from External_Book_Mapping.SGP.betway_mapper import get_static_mapping
from Settings.Models.base_models import TeamData, GameData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
import asyncio
from curl_cffi import AsyncSession as CurlAsyncSession


class OneBv(PPHBookBase):
    VALID_LEAGUES = ["NBA", "MLB", "NHL", "NFL", "CBB", "CFB"]

    # Filter out markets/leagues that are not relevant.
    ALLOWED_MARKETS = ["ncaa", "nfl", "nba", "mlb", "nhl", "national hockey league", "college football", "college basketball"]

    # Stop words to replace when filtering.
    STOP_WORDS = ["alternate", "game", "men", "women", "-", "basketball", "ncaab", "ncaa"]

    LEAGUE_NAME_MAPPER = {
        "national hockey league": "NHL",
        "ncaa": "NCAAW",
        "ncaab": "NCAAB"
    }

    def __init__(self):
        super().__init__(book_name="1bv")
        self.stat_mapping = get_static_mapping()
        # Contains the proper team names, as game lines section is the only section
        # that will have the proper team names, so we want to store here, so they can be referenced for the other sections,
        # that don't have the proper team names.
        self.league_dict = {}


    async def get_app_token(self):
        token_data = await self.api_caller(
            use_proxy=True,
            url=self.book_data.url.get("app_token_url"),
            method=self.book_data.method,
            headers=self.book_data.headers
        )



        return token_data.get("AppToken", None) if isinstance(token_data, dict) else None

    async def get_player_token(self, app_token: str):
        username = os.getenv("1BV_USERNAME")
        password = os.getenv("1BV_PASSWORD")

        if not username or not password:
            raise ValueError("Missing required environment variables: 1BV_USERNAME, 1BV_PASSWORD")

        headers = {
            **self.book_data.headers,
            'appToken': app_token,
        }

        token_data = await self.api_caller(
            url=self.book_data.url.get("player_token_url").format(username=username, password=password),
            use_proxy=True,
            method="POST",
            headers=headers,
        )

        return token_data.get("PlayerToken", None) if isinstance(token_data, dict) else None

    def market_helper(self, league_description: str, sport_id: str) -> str:
        """Used to help determine the market type"""
        if not league_description:
            return league_description


        league_description = self.LEAGUE_NAME_MAPPER.get(league_description.lower(), league_description)

        stop_words_copy = self.STOP_WORDS.copy()
        stop_words_copy.extend([sport_id.lower()])

        modified_league_description = " ".join(word for word in league_description.split() if word.lower() not in stop_words_copy)

        return modified_league_description.strip() if modified_league_description else "game lines"


    def build_league_ids(self, raw_league_data: dict, exclude_player_props: bool = True, league_filter: bool = True,
                         filter_markets: bool = True):
        league_ids = {}

        for data in raw_league_data.get("Groups", []):
            for league in data.get("Leagues", []):
                league_description = league.get("LeagueDescription", '').lower()
                sport_id = league.get("SportId", '').lower()

                if "player" in league_description and exclude_player_props:
                    continue

                # These are classified as main markets but this case we don't want them (ex. Hawks SC First).
                if "game props" in league_description:
                    continue

                if league_filter and league.get("SportId", '').upper() not in self.VALID_LEAGUES:
                    continue

                # Special condition as they list both of these as CBB for sport id.
                if "ncaa" in league_description and "women" in league_description:
                    sport_id = "ncaaw"
                elif "ncaa" in league_description:
                    sport_id = "ncaab"


                if filter_markets and not any(market in league_description for market in self.ALLOWED_MARKETS):
                    continue

                league_ids[league.get("LeagueId")] = {
                    "league_id": league.get("LeagueId"),
                    "sport_id": sport_id,
                    "api_sport_id": league.get("SportId"),
                    "raw_league_description": league_description,
                    "market_type": self.market_helper(league_description, league.get("SportId", '')),
                }


        return league_ids

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
        team_data = kwargs.get("team_data")
        team_a = team_data.team_a if team_data.team_a else ""
        team_b = team_data.team_b if team_data.team_b else ""

        base_mapper = kwargs.get("base_market_mapper")

        for bet_type, line_key, odds_key in [("Over", "TOTAL_OVER", "OVER_ODDS"), ("Under", "TOTAL_UNDER", "UNDER_ODDS")]:
            mapped_market_name = name_mapper_func(market_name=market_name, odds_key=odds_key, base_market_mapper=base_mapper)

            total_line = game_data.get(line_key)
            total_odds = game_data.get(odds_key)
            if not total_line or not total_odds:
                continue

            current_dict_name = game_data.get("VISITOR_TEAM", '').lower()
            team_name = team_a if team_a.lower() in current_dict_name else team_b

            odds.append(SportsbookStats(
                market=mapped_market_name,
                bet_team=team_name if "team totals" in market_name.lower() else None,
                line=abs(float(total_line)),
                bet_type=bet_type,
                future=False,
                odds_format=OddsFormat(american_odds=float(total_odds)),
            ))

        return odds


    async def build_market(self, event_data: dict, league_data: dict):
        family_id = event_data.get("FAMILY_GAME", '')

        # We use this, as some GAME_TYPE_IDS are = 1, yet they aren't the proper naming convention, so we do a conditional check.
        game_stat_id = event_data.get("GAME_STAT", "B")

        league_id = event_data.get("LEAGUE_ID", '')
        found_league = league_data.get(league_id, {})

        eastern = pytz.timezone("US/Eastern")

        raw_start_date = event_data.get("DATE_TIME_GAME", '')
        dt = datetime.fromisoformat(raw_start_date.replace("Z", ""))
        dt = eastern.localize(dt)
        new_dt = dt.astimezone(timezone.utc)
        start_date = new_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Store these ideas for future markets, as we can get the proper team names.
        if all([
            found_league.get("market_type", '').lower() == "game lines",
            # event_data.get("GAME_TYPE_ID", -1) in [1, 59],
            game_stat_id != "B",
        ]):
            self.league_dict[family_id] = {
                "home": re.sub(r'\s*.{2}#.*', '', event_data.get("HOME_TEAM", '')),
                "away": re.sub(r'\s*.{2}#.*', '', event_data.get("VISITOR_TEAM", '')),
            }

        team_data = TeamData(
            team_a=self.league_dict.get(family_id, {}).get("home") if family_id else event_data.get("HOME_TEAM", ''),
            team_b=self.league_dict.get(family_id, {}).get("away") if family_id else event_data.get("VISITOR_TEAM", '')
        )

        # Perform fuzzy matching, if no team data can be found.
        if not team_data.team_a or not team_data.team_b:
            game_description = event_data.get("GAME_DESCRIPTION", '')
            split_game = game_description.split("-")[0]
            versus_split = split_game.split(" vs ")

            all_teams = {
                full_name: teams
                for teams in self.league_dict.values()
                for full_name in [teams["home"], teams["away"]]
            }

            matched = []
            for versus in versus_split:
                result = process.extractOne(versus, all_teams.keys(), scorer=fuzz.partial_ratio, score_cutoff=70)

                if result:
                    matched.append(all_teams[result[0]])

            if matched:
                teams = matched[0]
                team_data = TeamData(
                    team_a=teams["home"],
                    team_b=teams["away"]
                )

        if not team_data.team_a or not team_data.team_b:
            return None


        game_key = self.generate_key([team_data.team_a, team_data.team_b, start_date])


        game_data = GameData(
            start_date=start_date,
            league=found_league.get("sport_id", ''),
            team_data=team_data,
            odds=[],
            game_key=game_key
        )

        market_name = found_league.get("market_type", '').lower()

        # Period events, contain the period number.
        if event_data.get("PERIOD", -1) != 0:
            period = event_data.get('VISITOR_TEAM', '').split( )[0]
            market_name = period if period else market_name


        home_odds_name = "HOME_ODDS" if event_data.get("HOME_ODDS", None) is not None else "HOME_SPECIAL_ODDS"
        away_odds_name = "VISITOR_ODDS" if event_data.get("VISITOR_ODDS", None) is not None else "VISITOR_SPECIAL_ODDS"


        home_spread_value_name = "HOME_SPECIAL" if event_data.get("HOME_SPECIAL", None) is not None else "HOME_SPREAD"
        home_spread_odds_name = "HOME_SPECIAL_ODDS" if event_data.get("HOME_SPECIAL_ODDS", None) is not None else "HOME_SPREAD_ODDS"

        away_spread_value_name = "VISITOR_SPECIAL" if event_data.get("VISITOR_SPECIAL", None) is not None else "VISITOR_SPREAD"
        away_spread_odds_name = "VISITOR_SPECIAL_ODDS" if event_data.get("VISITOR_SPECIAL_ODDS", None) is not None else "VISITOR_SPREAD_ODDS"

        base_market_mapper = {
            home_odds_name: "Moneyline",
            away_odds_name: "Moneyline",
            home_spread_odds_name: "Spread",
            away_spread_odds_name: "Spread",
            "OVER_ODDS": "Total",
            "UNDER_ODDS": "Total",
        }



        game_data.odds.extend(self.moneyline_type(team_data=team_data, game_data=event_data,
                                                  market_name=market_name,
                                                  name_mapper_func=self.name_mapper,
                                                  home_odds_name=home_odds_name, away_odds_name=away_odds_name, base_market_mapper=base_market_mapper))

        game_data.odds.extend(self.spread_type(team_data=team_data, game_data=event_data, market_name=market_name,
                                               name_mapper_func=self.name_mapper, home_spread_value_name=home_spread_value_name, away_spread_value_name=away_spread_value_name,
                                               home_spread_odds_name=home_spread_odds_name, away_spread_odds_name=away_spread_odds_name, base_market_mapper=base_market_mapper,
                                               league=found_league.get("sport_id", '')))


        game_data.odds.extend(self.total_type(game_data=event_data, market_name=market_name, name_mapper_func=self.name_mapper,
                                              team_data=team_data, base_market_mapper=base_market_mapper))

        return game_data if game_data.odds else None


    async def run_book(self):
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            app_token: str | None = await self.get_app_token()

            if not app_token:
                return

            player_token = await self.get_player_token(app_token=app_token)

            if not player_token:
                return

            raw_league_data = await self.api_caller(
                url=self.book_data.url.get("leagues_url"),
                use_proxy=True,
                method=self.book_data.method,
                headers={
                    **self.book_data.headers,
                    "appToken": app_token,
                    "playerToken": player_token
                },
            )

            league_ids = self.build_league_ids(raw_league_data=raw_league_data, exclude_player_props=True, league_filter=True, filter_markets=True)

            tasks = await asyncio.gather(
                *[
                    self.api_caller(
                        use_proxy=True,
                        url=self.book_data.url.get("event_url"),
                        method=self.book_data.method,
                        headers={
                            **self.book_data.headers,
                            "appToken": app_token,
                            "playerToken": player_token
                        },
                        params={
                            "leagueId": league_details.get("league_id"),
                            "loadAgentLines": "false",
                            "loadDefaultOdds": "false",
                            "sportId": league_details.get("api_sport_id"),
                            "loadMlbLines": "false",
                            "loadPropsEvents": "false",
                            "loadWagerTypeOnline": "false"
                        }
                    )

                    for league_details in league_ids.values()
                ]
            )

            # Flatten the list of events from the tasks and convert to a list if its not.
            events = [event for task in tasks for event in (task if isinstance(task, list) else [task])]

            events = list(chain.from_iterable(
                league["EVENTS"]
                for item in events
                if item.get("Events", {}).get("LEAGUES")
                for league in item["Events"]["LEAGUES"]
            ))

            event_data = {}

            for event in events:
                game_data = await self.build_market(event_data=event, league_data=league_ids)
                if game_data:
                    if game_data.game_key in event_data:
                        event_data[game_data.game_key].odds.extend(game_data.odds)
                    else:
                        event_data[game_data.game_key] = game_data


            onebv_data = list(event_data.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=onebv_data)

            # print(self.extract_market_names(mapped_data))

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )


            return mapped_data



if __name__ == "__main__":
    onebv = OneBv()
    asyncio.run(onebv.run_book())