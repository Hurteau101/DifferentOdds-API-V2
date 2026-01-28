import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData
from Utils.request_caller import SportbookRequestType


class DraftKingsPickSix(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="draftkings_6", request_type=SportbookRequestType.ASYNC)

    def _extract_league_keys(self, api_data: dict) -> list:
        return [
            data.get("sportLeagueKey")
            for data in api_data.get("sportLeagues", [])
            if data.get("hasPicksAvailable")
        ]

    def _extract_pickable_id_data(self, market_data: dict, market_names: dict, line_data: dict) -> GameData | None:
        """Extract all the player data from the pickable id data."""
        def extract_team_data(team_details: dict, player_name: str) -> dict:
            start_date = team_details.get("competitionSummary").get("startTime")

            # We check if there is . in time as they use milliseconds in some of the times.
            if "." in start_date:
                start_date = start_date.split(".")[0]

            player_team_city = team_details.get("team").get("city")
            player_team = f'{team_details.get("team").get("name")}'
            if player_team_city:
                player_team = f'{player_team_city} {player_team}'

            if team_details.get("competitionSummary").get("matchupDisplay").get(
                    "displayType").lower() != "team-vs-team":
                team_key = DraftKingsPickSix.generate_key([player_name, start_date])
                return {
                    "team_a": None,
                    "team_b": None,
                    "player_team": player_team,
                    "team_key": team_key,
                    "start_date": start_date,
                    "solo_game": True
                }

            home_city = team_details.get("competitionSummary").get("homeTeam").get("city")
            away_city = team_details.get("competitionSummary").get("awayTeam").get("city")

            team_a = f'{team_details.get("competitionSummary").get("homeTeam").get("name")}'
            team_b = f'{team_details.get("competitionSummary").get("awayTeam").get("name")}'

            team_a_abbreviation = team_details.get("competitionSummary").get("homeTeam").get("abbreviation")
            team_b_abbreviation = team_details.get("competitionSummary").get("awayTeam").get("abbreviation")

            team_key = DraftKingsPickSix.generate_key([team_a, team_b, start_date])

            if home_city:
                team_a = f'{home_city} {team_a}'

            if away_city:
                team_b = f'{away_city} {team_b}'

            return {
                "team_a": team_a,
                "team_b": team_b,
                "team_a_abbreviation": team_a_abbreviation,
                "team_b_abbreviation": team_b_abbreviation,
                "player_team": player_team,
                "team_key": team_key,
                "start_date": start_date,
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

        league = player_details.get("league").lower()

        groupId = market_data.get("pickGroupId", "")
        pickableId = market_data.get("pickableId", "")

        # Check in place as Esports, you need to know the maps for the stat type, so we add this check to ensure its added.
        if not player_details.get("solo_game") and player_details.get("total_competition_time"):
            game_length = player_details.get("total_competition_time").lower()
            stat_type = f"{game_length} {stat_type}"

        stat_type =stat_type.lower()

        return GameData(
            league=league,
            game_key=player_details.get("team_key"),
            start_date=player_details.get("start_date"),
            team_data=TeamData(
                team_a=player_details.get("team_a"),
                team_a_abbreviation=player_details.get("team_a_abbreviation"),
                team_b=player_details.get("team_b"),
                team_b_abbreviation=player_details.get("team_b_abbreviation"),
            ),
            odds=[
                DFSStats(
                    player_name=player_details.get("player_name"),
                    player_team=player_details.get("player_team"),
                    stat_type=stat_type,
                    future=True if "szn" in player_details.get("league").lower() else False,
                    line=active_markets.get("targetValue"),
                    bet_type=direction_mapper.get(str(stat.get("statLinePropositionId"))),
                    regular_line=True if stat.get("standingsMultiplier") == 1 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=stat.get("standingsMultiplier"),
                        betlink=self._generate_bet_link(
                            league=league,
                            groupId=groupId,
                            pickableId=pickableId,
                            direction=direction_mapper.get(str(stat.get("statLinePropositionId")))
                        ),
                    )
                )

                for stat in active_markets.get("activeSelections")

            ],
            solo_game=player_details.get("solo_game")
        )

    def _generate_bet_link(self, league: str, groupId: str, pickableId: str, direction: str) -> dict:
        mapper = {
            "over": "1",
            "under": "2"
        }

        base = "https://pick6.draftkings.com/?"
        sport = f"sport={league}&"
        pickGroup= f"pickGroup={groupId}&"
        pickable = f"picks={pickableId}%2B{mapper.get(direction)}"
        end = "&entrySource=shareLink"
        url = f"{base}{sport}{pickGroup}{pickable}{end}"

        single_url = f"{base}{sport}{pickGroup}{pickable}{end}"
        starter = f"{base}{sport}{pickGroup}{pickable}"
        middle_adder = f"{pickableId}%2B{mapper.get(direction)}%2C"
        end_adder = f"{pickableId}%2B{mapper.get(direction)}"


        return {
            "pickableId": pickableId,
            "groupId": groupId,
            "base": base,
            "sport": league,
            "side": direction,
            "url": url,
            "link_helper": {
                "single_url": single_url,
                "starter": starter,
                "middle_adder": middle_adder,
                "end_adder": end_adder,
                "end": end,
            }
        }

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_league_keys = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_list_url"),
                method="get",
                headers=self.book_data.headers,
            )

            if not api_league_keys:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league keys returned",
                    level="error"
                )
                return

            league_keys = self._extract_league_keys(api_league_keys)

            tasks = [

                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("league_ids_url").format(league_key=league_key),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league_key in league_keys
            ]

            league_results = await asyncio.gather(*tasks)

            if not league_results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            league_ids = [
                league.get("mainPickGroupId")
                for league in league_results
            ]

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("markets_url").format(league_id=league),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league in league_ids
            ]

            market_results = await asyncio.gather(*tasks)

            if not market_results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No market data returned",
                    level="error"
                )
                return

            lines_mapped = {
                market.get("pickableId"): market
                for result in market_results
                if result
                for market in result.get("activePickables", {})
            }

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("game_data_url").format(league_id=league),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league in league_ids
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No game data returned",
                    level="error"
                )
                return

            merged_data = [result for result in results]

            events = {}

            for game_details in merged_data:
                market_names_mapped = {
                    market.get("marketCategoryId"): market.get("marketName")
                    for market in game_details.get("marketCategories")
                }

                for pickable in game_details.get("pickables"):
                    player_data = self._extract_pickable_id_data(market_data=pickable, market_names=market_names_mapped, line_data=lines_mapped)
                    if player_data:
                        self.add_to_events(events, player_data, GameData)

            picksix_data = list(events.values())

            mapped_data = await self.external_mapper(picksix_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data