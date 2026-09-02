import os
from typing import Dict
import asyncio
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.dfs_base import DFSBookBase
from curl_cffi import AsyncSession as CurlAsyncSession
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Redis.redis_manager import RedisAsyncManager

class Chalkboard(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="chalkboard")
        self.league_data = {
            "CS2": ["Map 1-2 Headshots", "Map 1-2 Kills"],
            "LOL": ["Map 1-3 Kills", "Map 1-2 Kills"]
        }

    def _generate_payload(self, league_name: str, stat_list: list) -> dict:
        return {
            "structuredQuery": {
                "from": [
                    {
                        "collectionId": "dfs_legs"
                    }
                ],
                "where": {
                    "compositeFilter": {
                        "op": "AND",
                        "filters": [
                            {
                                "fieldFilter": {
                                    "field": {"fieldPath": "gameType"},
                                    "op": "IN",
                                    "value": {
                                        "arrayValue": {
                                            "values": [
                                                {"stringValue": f"{league_name.lower()}"}
                                            ]
                                        }
                                    }
                                }
                            },
                            {
                                "fieldFilter": {
                                    "field": {"fieldPath": "statisticName"},
                                    "op": "IN",
                                    "value": {
                                        "arrayValue": {
                                            "values": [
                                                {"stringValue": stat}
                                                for stat in stat_list
                                            ]
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

    def _extract_game_data(self, game_data: dict, margins: dict) -> GameData | None:
        document_name = game_data.get("document", {}).get("name", "")

        # There were duplicates, so add this logic check. Will have to check if this affects other leagues in the future.
        if not document_name.endswith("guaranteed-2"):
            return None

        base_map = game_data.get("document", {}).get("fields", {})
        if base_map.get("isLive", {}).get("booleanValue"):
            return None

        player_map = base_map.get("player", {}).get("mapValue", {}).get("fields", {})
        raw_league = base_map.get("gameType", {}).get("stringValue")
        league = raw_league.upper()
        start_date = base_map.get("displayScheduled", {}).get("stringValue")

        player_name = player_map.get("full_name", {}).get("stringValue")
        player_team_id = player_map.get("team_id", {}).get("stringValue")

        home_team = base_map.get("home", {}).get("mapValue", {}).get("fields", {})
        away_team = base_map.get("away", {}).get("mapValue", {}).get("fields", {})

        team_a = home_team.get("team_name", {}).get("stringValue")
        team_a_abbreviation = home_team.get("abbreviation", {}).get("stringValue")
        team_a_id = home_team.get("team_id", {}).get("stringValue")

        team_b = away_team.get("team_name", {}).get("stringValue")
        team_b_abbreviation = away_team.get("abbreviation", {}).get("stringValue")
        team_b_id = away_team.get("team_id", {}).get("stringValue")

        provider_id = base_map.get("providerId", {}).get("stringValue")

        margin_value = margins.get(provider_id, {}).get("doubleValue", 0) or margins.get(provider_id, {}).get("integerValue", 0)

        player_team = team_a if player_team_id == team_a_id else team_b if player_team_id == team_b_id else None

        if team_a and team_b:
            team_key = Chalkboard.generate_key([team_a, team_b, start_date])
        else:
            team_key = Chalkboard.generate_key([player_name, start_date])

        market_base = base_map.get("markets", {}).get("mapValue", {}).get("fields")

        stat_options = {
            "over": market_base.get("over", {}),
            "under": market_base.get("under", {})
        }

        if "nullValue" in stat_options.get("over") and "nullValue" in stat_options.get("under"):
            return None


        return GameData(
            league=league,
            start_date=start_date,
            game_key=team_key,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
                team_a_abbreviation=team_a_abbreviation,
                team_b_abbreviation=team_b_abbreviation
            ),
            odds=[
                DFSStats(
                    static_mapping=self.static_mapping,
                    player_name=player_name,
                    player_team=player_team,
                    future=False,
                    stat_type=stat.get("mapValue", {}).get("fields", {}).get("statisticName", {}).get("stringValue").lower(),
                    line=stat.get("mapValue", {}).get("fields", {}).get("value", {}).get("doubleValue"),
                    bet_type=direction,
                    regular_line=False,
                    optional_stats=OptionalStatInformation(
                        # "probabilities": stat.get("mapValue", {}).get("fields", {}).get("probabilities", {}).get("doubleValue"),
                        multiplier=self._calculate_ui(
                            margin=margin_value,
                            odds=float(stat.get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue", 0))
                        )
                    ),
                    odds_format=OddsFormat(
                        american_odds=float(
                            stat.get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue", 0))
                    ),
                )
                for direction, stat in stat_options.items()
                if stat.get("mapValue", {}).get("fields", {}).get("statisticName", {}).get("stringValue") is not None
            ],
            solo_game=False if all([team_a, team_b]) else True,
        )

    def _valid_return(self, returned_data: dict,  key_name: str) -> bool:
        """Validate returned data from Chalkboard API"""
        if not returned_data or not returned_data.get(key_name):
            return False

        return True

    def _calculate_ui(self, margin: float, odds: float) -> float:
        """Calculate UI multiplier"""
        modified_margin = 1 + margin
        ui_value = odds / modified_margin
        return round(ui_value, 2)


    async def _get_margin_odds_cutoff(self, session: CurlAsyncSession, headers: dict) -> Dict[str, dict]:
        """Retrieve margin and odds cutoff information from Chalkboard API"""
        margin_url = os.getenv("CHALKBOARD_MARGIN_URL")

        margin_data = await self.api_caller(
            session=session,
            url=margin_url,
            headers=headers,
            method="GET"
        )

        if self._valid_return(returned_data=margin_data, key_name="fields"):
            base_dict = margin_data.get("fields", {})
            margins = base_dict.get("margin", {}).get("mapValue", {}).get("fields", {})
            odds_cutoff = base_dict.get("oddsCutoff", {}).get("mapValue", {}).get("fields", {})
            return {
                "margins": margins,
                "odds_cutoff": odds_cutoff
            }

        return {}

    def stat_counter(self, player_data_dict: dict):
        from collections import Counter
        count = Counter()
        for data in player_data_dict.values():
            for stat in data.stats:
                count[stat.stat_type] += 1

        for c in count:
            print(f"{c}: {int(int(count[c]) / 2)}")

    async def run_book(self) -> list | None:
        redis_client = RedisAsyncManager(database=5)
        access_token = await redis_client.get_data("chalkboard_access_token")

        if not access_token:
            insert_log(
                key_name=self.book_data.title,
                error_type=ErrorTypes.AUTH,
                error_message="No access token found"
            )
            return None

        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url"),
                    headers=headers,
                    method=self.book_data.method,
                    json=self._generate_payload(league_name=league_name.lower(), stat_list=stat_list)
                )

                for league_name, stat_list in self.league_data.items()
            ]

            results = await asyncio.gather(*tasks)
            settings = await self._get_margin_odds_cutoff(session=session, headers=headers)

            merged_data = [result for result in results if result]

            if not merged_data:
                insert_log(
                    key_name=self.book_data.title,
                    error_type=ErrorTypes.API_NO_DATA,
                    error_message="No API data found"
                )
                return None

            events = {}

            for league in merged_data:
                for game in league:
                    player_data = self._extract_game_data(game_data=game, margins=settings.get("margins", {}))
                    if player_data:
                        self.add_to_events(events, player_data, GameData)

            chalkboard_data = list(events.values())

            if not chalkboard_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.NO_EXTRACTION_DATA,
                    error_message="No event data found"
                )
                return None

            await self.store_data(
                data_to_store=chalkboard_data,
                key_name=self.book_data.name
            )

            return chalkboard_data