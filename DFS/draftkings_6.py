import re
import aiohttp
import asyncio
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from datetime import datetime
from Settings.book_base import SportbookRequestType


class DraftKingsPickSix(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="draftkings_6")
        self.URL_PART = "&_data=routes%2F_homeShared"


    def _extract_leagues(self, league_data):
        return [
            {
                "league": league.get("league", {}).get("leagueAbbreviation").replace(" ", "+"),
                "unique": False,
            }
            for league in league_data.get("sportLeagues", {})
        ]

    # Extract the league name from the image url, as the unique names don't have a specific league.
    def _get_league_name(self, league_data):
        # Gather all possible links with league names.
        candidates = [
            league_data.get("homeTeam", {}).get("imageUrl"),
            league_data.get("awayTeam", {}).get("imageUrl"),
            league_data.get("imageUrl"),
        ]

        # Use regex to find the league name in the image URL. Filter out None values first to avoid errors.
        for url in filter(None, candidates):
            match = re.search(r'(?<=/images/)[^/]+', url)
            if match:
                return match.group(0)

        # Fall back if no league's can be found in the image URLs.
        return league_data.get("name")

    # Extract unique leagues from the API data, which are leagues that are not in the regular league section.
    def _extract_unique_leagues(self, league_data):
        return [
            {
                "league": self._get_league_name(league),
                "unique": True,
                "url_addon": f"https://pick6.draftkings.com{league.get('destination')}{self.URL_PART}"
            }

            for league in league_data.get("carouselLinks", []).get("sportLeagueKeyToLinks").get("21-125").get("rightAttachedLinks", [])
        ]

    # Generate URLs for each league, using the main URL for regular leagues and a unique URL for special leagues.
    def _generate_urls(self, league_data):
        return [
            self.book_data.url.get("main_url").format(league=league.get("league"))
            if not league.get("unique") else league.get("url_addon")

            for league in league_data
        ]


    def _extract_team_data(self, team_details, player_name):
        start_date = team_details.get("competitionSummary").get("startTime")

        # We check if there is . in time as they use milliseconds in some of the times.
        if "." in start_date:
            start_date = start_date.split(".")[0]

        player_team = self.clean_and_normalize_name(f'{team_details.get("team").get("name")} {team_details.get("team").get("name")}')

        if team_details.get("competitionSummary").get("matchupDisplay").get("displayType").lower() != "team-vs-team":
            team_key = self._generate_key([player_name, start_date])
            return {
                "team_a": None,
                "team_b": None,
                "player_team": player_team,
                "team_key": team_key,
                "start_date": self.cache_time(start_date),
                "solo_game": True
            }

        team_a = f'{team_details.get("competitionSummary").get("homeTeam").get("name")} {team_details.get("competitionSummary").get("homeTeam").get("city")}'
        team_b = f'{team_details.get("competitionSummary").get("awayTeam").get("name")} {team_details.get("competitionSummary").get("awayTeam").get("city")}'
        team_key = self._generate_key([team_a, team_b, start_date])

        return {
            "team_a": self.clean_and_normalize_name(team_a),
            "team_b": self.clean_and_normalize_name(team_b),
            "player_team": player_team,
            "team_key": team_key,
            "start_date": self.cache_time(start_date),
            "solo_game": False
        }

    def _extract_game_data(self, game_details):
        player_details = next((
            {
                "player_name": player_details.get("displayName"),
                "league": game_details.get("competitionSummary").get("leagueAbbreviation"),
                **self._extract_team_data(game_details, player_details.get("displayName")),
                "total_competition_time": game_details.get("competitionSummary").get("totalCompetitionTime")

            }

            for player_details in game_details.get("pickable").get("pickableEntities", [])
            for game_details in player_details.get("pickableCompetitions")
            if not game_details.get("competitionSummary").get("isLive")
        ), None)


        if not player_details:
            return None

        pick_group_id = game_details.get("pickGroupId")

        # Draftking uses More or Less, so this maps it to over and under.
        direction_mapper = {
            "1": "over",
            "2": "under",
        }

        # Check in place as Esports, you need to know the maps for the stat type, so we add this check to ensure its added.
        if not player_details.get("solo_game") and player_details.get("total_competition_time"):
            stat_type = STAT_TYPES.get(player_details.get("total_competition_time").lower(), player_details.get("total_competition_time")).title()
        else:
            stat_type = game_details.get("pickable").get("marketCategory").get("marketName")
            stat_type = STAT_TYPES.get(stat_type.lower(), stat_type).title()

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_details.get("player_name")),
            league=LEAGUES.get(player_details.get("league").lower(), player_details.get("league").upper()),
            start_date=player_details.get("start_date"),
            team_data=TeamData(
                team_a=player_details.get("team_a"),
                team_b=player_details.get("team_b"),
                team_key=player_details.get("team_key"),
                player_team=player_details.get("player_team"),
            ),
            stats=[
                Stats(
                    stat_type=stat_type,
                    line=game_details.get("activeMarket").get("targetValue"),
                    bet_direction=direction_mapper.get(str(stat.get("statLinePropositionId"))),
                    regular_line=True if stat.get("standingsMultiplier") == 1 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=stat.get("standingsMultiplier")
                    )
                )

                for stat in game_details.get("activeMarket").get("activeSelections")

            ],
            future=True if "szn" in player_details.get("league").lower() else False,
            solo_game=player_details.get("solo_game")
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_league_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("alternate_url"),
                method="get",
                headers=self.book_data.headers,
            )

            leagues = self._extract_leagues(api_league_data)
            unique_leagues = self._extract_unique_leagues(api_league_data)
            if unique_leagues:
                leagues.extend(unique_leagues)

            urls = self._generate_urls(leagues)

            tasks = [
                self.api_caller(
                    session=session,
                    url=link,
                    method=self.book_data.method,
                    headers=self.book_data.headers,
                )

                for link in urls
            ]

            results = await asyncio.gather(*tasks)
            merged_data = [item for res in results for key, item in res.get("pickableIdToPickableMap").items()]

            player_data_list = {}

            for game_details in merged_data:
                self._extract_game_data(game_details)
                player_data = self._extract_game_data(game_details)
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
    import asyncio
    draftkings = DraftKingsPickSix()
    asyncio.run(draftkings.run_book())
