import re
import aiohttp
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.book_base import SportbookRequestType
import asyncio

class DraftKingsPickSix(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="draftkings_6")

    def _extract_league_keys(self, api_data):
        return [
            data.get("sportLeagueKey")
            for data in api_data.get("sportLeagues", [])
            if data.get("hasPicksAvailable")
        ]

    def _extract_pickable_id_data(self, market_data, market_names, line_data):
        """Extract all the player data from the pickable id data."""
        def extract_team_data(team_details, player_name):
            start_date = team_details.get("competitionSummary").get("startTime")

            # We check if there is . in time as they use milliseconds in some of the times.
            if "." in start_date:
                start_date = start_date.split(".")[0]

            player_team_city = team_details.get("team").get("city")
            player_team = self.clean_and_normalize_name(f'{team_details.get("team").get("name")}')
            if player_team_city:
                player_team = self.clean_and_normalize_name(f'{player_team_city} {player_team}')

            if team_details.get("competitionSummary").get("matchupDisplay").get(
                    "displayType").lower() != "team-vs-team":
                team_key = self._generate_key([player_name, start_date])
                return {
                    "team_a": None,
                    "team_b": None,
                    "player_team": player_team,
                    "team_key": team_key,
                    "start_date": self.cache_time(start_date),
                    "solo_game": True
                }

            home_city = team_details.get("competitionSummary").get("homeTeam").get("city")
            away_city = team_details.get("competitionSummary").get("awayTeam").get("city")

            team_a = f'{team_details.get("competitionSummary").get("homeTeam").get("name")}'
            team_b = f'{team_details.get("competitionSummary").get("awayTeam").get("name")}'

            team_a_abbreviation = team_details.get("competitionSummary").get("homeTeam").get("abbreviation")
            team_b_abbreviation = team_details.get("competitionSummary").get("awayTeam").get("abbreviation")

            team_key = self._generate_key([team_a, team_b, start_date])

            if home_city:
                team_a = f'{home_city} {team_a}'

            if away_city:
                team_b = f'{away_city} {team_b}'

            return {
                "team_a": self.clean_and_normalize_name(team_a),
                "team_b": self.clean_and_normalize_name(team_b),
                "team_a_abbreviation": team_a_abbreviation,
                "team_b_abbreviation": team_b_abbreviation,
                "player_team": player_team,
                "team_key": team_key,
                "start_date": self.cache_time(start_date),
                "solo_game": False
            }

        player_details = next((
            {
                "player_name": player_details.get("displayName"),
                "league": game_details.get("competitionSummary").get("leagueAbbreviation"),
                **extract_team_data(game_details, player_details.get("displayName")),
                "total_competition_time": game_details.get("competitionSummary").get("totalCompetitionTime")

            }

            for player_details in market_data.get("pickableEntities", [])
            for game_details in player_details.get("pickableCompetitions")
            if not game_details.get("competitionSummary").get("isLive")
        ), None)


        if not player_details:
            return None

        # Draftking uses More or Less, so this maps it to over and under.
        direction_mapper = {
            "1": "over",
            "2": "under",
        }

        market_id = market_data.get("marketCategoryId")
        stat_type = market_names.get(market_id)

        lines_id = market_data.get("pickableId")
        line_data = line_data.get(lines_id, {})
        if not line_data or line_data.get("isUnpickable") or not stat_type:
            return None

        active_markets = line_data.get("activeMarkets")[0] if len(line_data.get("activeMarkets")) > 0 else {}

        if not active_markets or active_markets.get("isPaused"):
            return None


        # Check in place as Esports, you need to know the maps for the stat type, so we add this check to ensure its added.
        if not player_details.get("solo_game") and player_details.get("total_competition_time"):
            game_length = player_details.get("total_competition_time").lower()
            stat_type = f"{game_length} {stat_type}"

        stat_type = STAT_TYPES.get(stat_type.lower(), stat_type).title()

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_details.get("player_name")),
            league=LEAGUES.get(player_details.get("league").lower(), player_details.get("league").upper()),
            start_date=player_details.get("start_date"),
            team_data=TeamData(
                team_a=player_details.get("team_a"),
                team_a_abbreviation=player_details.get("team_a_abbreviation"),
                team_b=player_details.get("team_b"),
                team_b_abbreviation=player_details.get("team_b_abbreviation"),
                team_key=player_details.get("team_key"),
                player_team=player_details.get("player_team"),
            ),
            stats=[
                Stats(
                    stat_type=stat_type,
                    line=active_markets.get("targetValue"),
                    bet_direction=direction_mapper.get(str(stat.get("statLinePropositionId"))),
                    regular_line=True if stat.get("standingsMultiplier") == 1 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=stat.get("standingsMultiplier")
                    )
                )

                for stat in active_markets.get("activeSelections")

            ],
            future=True if "szn" in player_details.get("league").lower() else False,
            solo_game=player_details.get("solo_game")
        )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            raw_api_league_keys = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_list_url"),
                method="get",
                headers=self.book_data.headers,
            )

            api_league_keys = self.check_api_response(sportsbook="draftkings_6", results=raw_api_league_keys)
            if not api_league_keys:
                return

            league_keys = self._extract_league_keys(api_league_keys)

            tasks = [

                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("league_ids_url").format(league_key=league_key),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league_key in league_keys
            ]

            raw_league_results = await asyncio.gather(*tasks)

            league_results = self.check_api_response(sportsbook="draftkings_6", results=raw_league_results)

            if not league_results:
                return

            league_ids = [
                league.get("mainPickGroupId")
                for league in league_results
            ]

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("markets_url").format(league_id=league),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league in league_ids
            ]

            raw_market_results = await asyncio.gather(*tasks)

            market_results = self.check_api_response(sportsbook="draftkings_6", results=raw_market_results)

            if not market_results:
                return


            lines_mapped = {
                market.get("pickableId"): market
                for result in market_results
                if result
                for market in result.get("activePickables", {})
            }

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("game_data_url").format(league_id=league),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league in league_ids
            ]

            raw_results = await asyncio.gather(*tasks)

            results = self.check_api_response(sportsbook="draftkings_6", results=raw_results)

            if not results:
                return

            merged_data = [result for result in results]

            player_data_list = {}

            for game_details in merged_data:
                market_names_mapped = {
                    market.get("marketCategoryId"): market.get("marketName")
                    for market in game_details.get("marketCategories")
                }

                for pickable in game_details.get("pickables"):
                    player_data = self._extract_pickable_id_data(market_data=pickable, market_names=market_names_mapped, line_data=lines_mapped)
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

            picksix_data = list(player_data_list.values())
            return await self._database_mapper(picksix_data)

if __name__ == "__main__":
    draftkings = DraftKingsPickSix()
    asyncio.run(draftkings.run_book())
