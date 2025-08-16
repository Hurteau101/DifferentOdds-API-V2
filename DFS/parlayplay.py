import re

import aiohttp

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

        return True if player.get("match").get("league").get("leagueDescription").lower() in ["szn", "season"] else False

    # Check if it's a solo sport
    def _check_solo_sport(self, player):
        league = LEAGUES.get(player.get("match", {}).get("league", {}).get("leagueNameShort", "").lower(),
                             player.get("match", {}).get("league", {}).get("leagueNameShort", "").upper())

        if league in self.SOLO_SPORTS:
            return True

        return False if (player.get("match", {}).get("homeTeam", {}).get("teamname") and
                         player.get("match", {}).get("awayTeam", {}).get("teamname")) else True


    def _extract_data(self, game_data):
        return [
            PlayerData(
                player_name=player.get("player").get("fullName"),
                league=LEAGUES.get(player.get("match").get("league").get("leagueNameShort").lower(),
                                   player.get("match").get("league").get("leagueNameShort")).upper(),
                start_date=player.get("match").get("matchDate"),
                team_data=self._extract_team_data(game_data=player),
                future=Parlayplay._season_checker(player),
                solo_game=self._check_solo_sport(player),
                combo=False,
                stats=[
                    Stats(
                        stat_type=STAT_TYPES.get(stat.get("marketName").lower(), stat.get("marketName")).title(),
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
            for player in game_data.get("players")
        ]


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                dfs_book="parlayplay",
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method
            )

            if not api_data:
                self._api_call_log("parlayplay")
                return

            parlay_data = self._extract_data(api_data)
            return await self._database_mapper(parlay_data)

if __name__ == "__main__":
    parlayplay = Parlayplay()
    import asyncio
    asyncio.run(parlayplay.run_book())