import re
import aiohttp
import asyncio
from Mapper.static_mapper import LEAGUES, MARKET_TYPE_MAPPER, STAT_TYPES
from Settings.dfs_book_base import DFSBookBase
from Settings.book_base import SportbookRequestType
from Settings.dfs_model import PlayerData, TeamData, Stats, OptionalStatInformation, Odds, Discounts


class Parlayplay(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="parlayplay")
        self.SOLO_SPORTS = ["PGA", "EUROGOLF", "UFC"]

    # Extract team data
    def _extract_team_data(self, game_data):
        team_a = game_data.get("match", {}).get("homeTeam", {}).get("teamname")

        team_a_abbreviation = game_data.get("match", {}).get("homeTeam", {}).get("teamAbbreviation")

        team_b = game_data.get("match", {}).get("awayTeam", {}).get("teamname")
        team_b_abbreviation = game_data.get("match", {}).get("awayTeam", {}).get("teamAbbreviation")

        player_team = game_data.get("player", {}).get("team", {}).get("teamname")

        start_date = self.cache_time(game_data.get("match", {}).get("matchDate"))


        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([game_data.get("player", {}).get("fullName"), start_date])


        return TeamData(
                    team_a=self.clean_and_normalize_name(team_a),
                    team_b=self.clean_and_normalize_name(team_b),
                    player_team=self.clean_and_normalize_name(player_team),
                    team_a_abbreviation=self.clean_and_normalize_name(team_a_abbreviation),
                    team_b_abbreviation=self.clean_and_normalize_name(team_b_abbreviation),
                    team_key=team_key
                )

    # Check if it's a season stat type
    @staticmethod
    def _season_checker(player):
        league = player.get("match", {}).get("league", {}).get("leagueNameShort", "").lower()
        league = LEAGUES.get(league.lower(), league)

        if re.search("r(szn|season)", league, re.IGNORECASE):
            return True

        league_description = player.get("match", {}).get("league", {}).get("leagueDescription")

        if not league_description:
            return False

        return True if league_description.lower() in ["szn", "season"] else False

    # Check if it's a solo sport
    def _check_solo_sport(self, player):
        league = LEAGUES.get(player.get("match", {}).get("league", {}).get("leagueNameShort", "").lower(),
                             player.get("match", {}).get("league", {}).get("leagueNameShort", "").upper())

        if league in self.SOLO_SPORTS:
            return True

        return False if (player.get("match", {}).get("homeTeam", {}).get("teamname") and
                         player.get("match", {}).get("awayTeam", {}).get("teamname")) else True


    def _extract_data(self, player):
        def configure_stat_type(stat_type):
            stat_type = stat_type.replace("Player", "").strip()
            stat_type = " ".join(stat_type.split())
            stat_type = STAT_TYPES.get(stat_type.lower(), stat_type)
            return stat_type

        return PlayerData(
            player_name=player.get("player").get("fullName"),
            league=LEAGUES.get(player.get("match").get("league").get("leagueNameShort").lower(),
                               player.get("match").get("league").get("leagueNameShort")).upper(),
            start_date=self.cache_time(player.get("match").get("matchDate")),
            team_data=self._extract_team_data(game_data=player),
            future=Parlayplay._season_checker(player),
            solo_game=self._check_solo_sport(player),
            combo=False,
            stats=[
                Stats(
                    stat_type=configure_stat_type(stat.get("marketName")),
                    line=stat.get("selectionPoints"),
                    bet_direction=option,
                    regular_line=True if price_key == 1.00 else False,
                    optional_stats=OptionalStatInformation(
                        market_type=MARKET_TYPE_MAPPER.get(stat.get("matchPeriod").lower(), stat.get("matchPeriod")) if stat.get("matchPeriod") else None,
                        multiplier=stat.get("decimalPriceOver") if option == "over" else stat.get("decimalPriceUnder"),
                        odds=Odds(
                            boosted_payout=True if base_stat.get("isBoostedPayout") else False,
                        )
                    ),
                )

                for base_stat in player.get("stats")
                for stat in base_stat.get("altLines").get("values")
                for option, price_key in [("over", "decimalPriceOver"), ("under", "decimalPriceUnder")]
                if stat.get(price_key, 0) != 0
            ]
        )

    async def _get_leagues(self, session):
        raw_league_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("league_url"),
            method=self.book_data.method
        )

        league_data = self.check_api_response(sportsbook="parlayplay", results=raw_league_data)
        if not league_data:
            return

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
                return

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url").format(sport=league.get("sport"), league=league.get("league"), period=period),
                    method=self.book_data.method
                )

                for league in league_data
                for period in league.get("market_periods", [])
            ]

            raw_results = await asyncio.gather(*tasks)
            results = self.check_api_response(sportsbook="parlayplay", results=raw_results)
            if not results:
                return

            api_data = [result for result in results if result]

            player_data_list = {}

            for result in api_data:
                for player in result.get("players"):
                    player_data = self._extract_data(player)
                    if player_data:
                        player_key = (
                            player_data.player_name,
                            player_data.team_data.team_a,
                            player_data.team_data.team_b,
                            player_data.start_date,
                        )

                        if player_key in player_data_list:
                            player_data_list[player_key].stats.extend(player_data.stats)
                        else:
                            player_data_list[player_key] = player_data

            parlay_data = list(player_data_list.values())
            return await self._database_mapper(parlay_data)

if __name__ == "__main__":
    parlayplay = Parlayplay()
    import asyncio
    asyncio.run(parlayplay.run_book())