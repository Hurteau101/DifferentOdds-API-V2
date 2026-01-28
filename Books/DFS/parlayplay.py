import asyncio
import re
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData
from Utils.request_caller import SportbookRequestType


class Parlayplay(DFSBookBase):
    SOLO_SPORTS = [
        "PGA",
        "EUROGOLF",
        "UFC"
    ]
    def __init__(self):
        super().__init__(book_name="parlayplay", request_type=SportbookRequestType.ASYNC)

        # Extract team data

    def _extract_team_data(self, game_data: dict) -> dict:
        team_a = game_data.get("match", {}).get("homeTeam", {}).get("teamname")

        team_a_abbreviation = game_data.get("match", {}).get("homeTeam", {}).get("teamAbbreviation")

        team_b = game_data.get("match", {}).get("awayTeam", {}).get("teamname")
        team_b_abbreviation = game_data.get("match", {}).get("awayTeam", {}).get("teamAbbreviation")

        player_team = game_data.get("player", {}).get("team", {}).get("teamname")

        start_date = game_data.get("match", {}).get("matchDate")

        if team_a and team_b:
            team_key = Parlayplay.generate_key([team_a, team_b, start_date])
        else:
            team_key = Parlayplay.generate_key([game_data.get("player", {}).get("fullName"), start_date])

        return {
            "team_a":team_a,
            "team_b":team_b,
            "player_team":player_team,
            "team_a_abbreviation":team_a_abbreviation,
            "team_b_abbreviation":team_b_abbreviation,
            "team_key":team_key
        }

    @staticmethod
    def _season_checker(player: dict) -> bool:
        league = player.get("match", {}).get("league", {}).get("leagueNameShort", "").lower()

        if re.search("r(szn|season)", league, re.IGNORECASE):
            return True

        league_description = player.get("match", {}).get("league", {}).get("leagueDescription")

        if not league_description:
            return False

        return True if league_description.lower() in ["szn", "season"] else False

    # Check if it's a solo sport
    def _check_solo_sport(self, player):
        league = player.get("match", {}).get("league", {}).get("leagueNameShort", "")

        if league in self.SOLO_SPORTS:
            return True

        return False if (player.get("match", {}).get("homeTeam", {}).get("teamname") and
                         player.get("match", {}).get("awayTeam", {}).get("teamname")) else True

    def _extract_data(self, player: dict) -> GameData:
        def configure_stat_type(stat_type: str) -> str:
            stat_type = stat_type.replace("Player", "").strip()
            stat_type = " ".join(stat_type.split())
            return stat_type

        team_data = self._extract_team_data(game_data=player)

        return GameData(
            league=player.get("match").get("league").get("leagueNameShort"),
            start_date=player.get("match").get("matchDate"),
            game_key=team_data.get("team_key"),
            team_data=TeamData(
                team_a=team_data.get("team_a"),
                team_b=team_data.get("team_b"),
                team_a_abbreviation=team_data.get("team_a_abbreviation"),
                team_b_abbreviation=team_data.get("team_b_abbreviation"),
            ),
            solo_game=self._check_solo_sport(player),
            odds=[
                DFSStats(
                    player_name=player.get("player").get("fullName"),
                    player_team=team_data.get("player_team"),
                    stat_type=configure_stat_type(stat.get("marketName")),
                    future=Parlayplay._season_checker(player),
                    line=stat.get("selectionPoints"),
                    bet_type=option,
                    regular_line=True if price_key == 1.00 else False,
                    optional_stats=OptionalStatInformation(
                        market_type=Parlayplay.return_market_mapper().get(stat.get("matchPeriod").lower(),
                                              stat.get("matchPeriod")) if stat.get(
                            "matchPeriod") else None,
                        multiplier=stat.get("decimalPriceOver") if option == "over" else stat.get("decimalPriceUnder"),
                        boosted_payout=True if base_stat.get("isBoostedPayout") else False,
                    ),
                )

                for base_stat in player.get("stats")
                for stat in base_stat.get("altLines").get("values")
                for option, price_key in [("over", "decimalPriceOver"), ("under", "decimalPriceUnder")]
                if stat.get(price_key, 0) != 0
            ]
        )

    async def _get_leagues(self, session: aiohttp.ClientSession) -> list:
        league_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("league_url"),
            method=self.book_data.method
        )

        if not league_data:
            return []

        league_list = [
            {
                "sport": sport_name,
                "league": league_name,
                "market_periods": market_periods
            }

            for sport_name, league_information in league_data.get("matchPeriods", {}).items()
            for league_name, market_periods in league_information.items()
        ]

        for other_sports in league_data.get("sportsData", {}).get("sports", []):
            for leagues in other_sports.get("leagues", []):
                other_sport_name = other_sports.get("sportName")
                other_league_name = leagues.get("leagueNameShort")

                exists = any(
                    check_league["sport"] == other_sport_name and check_league["league"] == other_league_name
                    for check_league in league_list
                )

                if not exists:
                    league_list.append({
                        "sport": other_sport_name,
                        "league": other_league_name,
                        "market_periods": [""]
                    })

        return league_list

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self._get_leagues(session)
            if not league_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("main_url").format(sport=league.get("sport"),
                                                                  league=league.get("league"), period=period),
                    method=self.book_data.method
                )

                for league in league_data
                for period in league.get("market_periods", [])
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No market data returned",
                    level="error"
                )
                return

            api_data = [result for result in results if result]

            events = {}

            for result in api_data:
                for player in result.get("players"):
                    player_data = self._extract_data(player)
                    if player_data:
                        self.add_to_events(events, player_data, GameData)


            parlay_data = list(events.values())

            mapped_data = await self.external_mapper(parlay_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data