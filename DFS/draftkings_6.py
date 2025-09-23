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

    def _extract_leagues(self, api_data):
        leagues = []
        for data in api_data.get("carouselPills", []):
            # Custom has a unique route to call.
            if data.get("carouselPillType") == "Custom":
                # Destination holds a part of the URL param we need for custom leagues.
                destination = data.get("customPillData", {}).get("destination", "N/A")
                match = re.search(r"^/events/([^/]+)/", destination)
                if match:
                    league = match.group(1)
                    leagues.append({
                        "league": f"CUSTOM_{league}",
                        "unique_route": destination,
                        "custom": True
                    })
            elif data.get("sportLeaguePillData", {}).get("hasPicksAvailable"):
                leagues.append({
                    "league": data.get("sportLeaguePillData", {}).get("leagueAbbreviation"),
                    "custom": False
                })

        return leagues

    def _map_card_data(self, api_data):
        return {
            data.get("pickableId"): {
                "name_id": next(entity["dkId"] for entity in data.get("entities", [])),
                "stat_id": data.get("marketCategoryId"),
                "game_id": next(compid for entity in data.get("entities", []) for compid in entity.get("compIds", [])),
            }
            for data in api_data.get("pickCardsByPickGroup", {}).get("pickCards", [])
            if data.get("entities")
        }

    def _map_game_data(self, api_data):
        return {
            data.get("competitionId"): {
                "league": data.get("sport"),
                "start_time": data.get("startTime"),
                "solo_game": True if data.get("matchupDisplay", {}).get("displayType") == "head-to-head" else False,
                "home_team": data.get("homeTeam", {}),
                "away_team": data.get("awayTeam", {}),
            }
            for data in api_data
        }


    def _extract_pick_card_data(self, name_mapping, card_mapping, stat_mapping, game_mapping, market_data):
        """Extract all the player data from the pick card data."""
        if market_data.get("isUnpickable"):
            return None

        mapping_ids = card_mapping.get(market_data.get("pickableId"))
        player_details = name_mapping.get(str(mapping_ids.get("name_id")))
        stat_details = stat_mapping.get(str(mapping_ids.get("stat_id")))
        game_details = game_mapping.get(mapping_ids.get("game_id"))

        if any([not player_details, not stat_details, not game_details]):
            return None

        player_name = player_details.get("fullName")

        if not game_details.get("solo_game"):
            team_a = f"{game_details.get('home_team', {}).get('name', {}) or ''} {game_details.get('home_team', {}).get('city') or ''}"
            team_b = f"{game_details.get('away_team', {}).get('name', {}) or ''} {game_details.get('away_team', {}).get('city') or ''}"
            team_a_abbreviation = game_details.get("home_team", {}).get("abbreviation")
            team_b_abbreviation = game_details.get("away_team", {}).get("abbreviation")

            team_key = self._generate_key([team_a, team_b, self.cache_time(game_details.get("start_time"))])
        else:
            team_a = None
            team_b = None
            team_a_abbreviation = None
            team_b_abbreviation = None
            team_key = self._generate_key([player_name, self.cache_time(game_details.get("start_time"))])

        direction_mapper = {
            "1": "over",
            "2": "under",
        }

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_details.get("fullName")),
            league=LEAGUES.get(game_details.get("league").lower(), game_details.get("league")),
            start_date=self.cache_time(game_details.get("start_time")),
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
                team_key=team_key,
                player_team=player_name,
                team_a_abbreviation=team_a_abbreviation,
                team_b_abbreviation=team_b_abbreviation,
            ),
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(stat_details.get("name").lower(), stat_details.get("name")).title(),
                    line=market.get("targetValue"),
                    bet_direction=direction_mapper.get(str(selection.get("statLinePropositionId"))),
                    regular_line=True if selection.get("standingsMultiplier") == 1 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=selection.get("standingsMultiplier")
                    )
                )
                for market in market_data.get("activeMarkets", [])
                for selection in market.get("activeSelections", [])
            ],
            future=True if "szn" in game_details.get("league").lower() else False,
            solo_game=game_details.get("solo_game")
        )

    def _extract_pickable_id_data(self, market_data):
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

            for player_details in market_data.get("pickable").get("pickableEntities", [])
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

        # Check in place as Esports, you need to know the maps for the stat type, so we add this check to ensure its added.
        if not player_details.get("solo_game") and player_details.get("total_competition_time"):
            stat_type = STAT_TYPES.get(player_details.get("total_competition_time").lower(),
                                       player_details.get("total_competition_time")).title()
        else:
            stat_type = market_data.get("pickable").get("marketCategory").get("marketName")
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
                    line=market_data.get("activeMarket").get("targetValue"),
                    bet_direction=direction_mapper.get(str(stat.get("statLinePropositionId"))),
                    regular_line=True if stat.get("standingsMultiplier") == 1 else False,
                    optional_stats=OptionalStatInformation(
                        multiplier=stat.get("standingsMultiplier")
                    )
                )

                for stat in market_data.get("activeMarket").get("activeSelections")

            ],
            future=True if "szn" in player_details.get("league").lower() else False,
            solo_game=player_details.get("solo_game")
        )

    def _merge_player_data(self, player_data_list, player_data):
        """Merge player_data into player_data_list"""
        if not player_data:
            return

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

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_league_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("leagues_url"),
                method="get",
                headers=self.book_data.headers,
            )

            if not api_league_data:
                self.file_logger.log(
                    message="Couldn't map leagues for DraftKings Pick 6",
                )
                return

            leagues = self._extract_leagues(api_league_data)

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url").format(league=league.get("league")) if not league.get("custom") else
                    self.book_data.url.get("unique_url").format(event=league.get("unique_route")),
                    method="get",
                    headers=self.book_data.headers,
                )

                for league in leagues
            ]

            results = await asyncio.gather(*tasks)
            if not results:
                self._api_call_log("draftkings_6")
                return

            merged_data = [result for result in results]

            player_data_list = {}

            for game_details in merged_data:
                has_pick_card = game_details.get("pickCardData")
                has_pickable_id = game_details.get("pickableIdToPickableMap")
                game_map = self._map_game_data(game_details.get("allCompetitions"))

                if has_pick_card:
                    # Holds the map to all the player names.
                    name_map = has_pick_card.get("pickCardsByPickGroup", {}).get("entityInfoByDkId")

                    # Grabs the pickableId and maps to the dkId (aka player id)
                    card_map = self._map_card_data(has_pick_card)

                    # Holds the stat map
                    stat_map = has_pick_card.get("pickCardsByPickGroup", {}).get("marketPillByCategoryId")

                    # Pass in the name map and card map to map specific player details as well as market details.
                    for game_data in has_pick_card.get("activePickables", {}):
                        player_data = self._extract_pick_card_data(name_mapping=name_map, card_mapping=card_map,
                                                                   stat_mapping=stat_map, game_mapping=game_map,
                                                                   market_data=game_data)

                        self._merge_player_data(player_data_list, player_data)

                elif has_pickable_id:
                    for game_data in game_details.get("pickableIdToPickableMap", {}).values():
                        player_data = self._extract_pickable_id_data(game_data)
                        self._merge_player_data(player_data_list, player_data)
                else:
                    continue

            picksix_data = list(player_data_list.values())
            return await self._database_mapper(picksix_data)

if __name__ == "__main__":
    draftkings = DraftKingsPickSix()
    asyncio.run(draftkings.run_book())
