import os
from typing import Dict

import aiohttp
from dotenv import load_dotenv
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from DFS.chalkboard_league_data import chalkboard_leagues
from Redis.redis_manager import RedisManager
from Settings.dfs_model import PlayerData, Stats, TeamData, Discounts
import asyncio


class Chalkboard(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="chalkboard")
        self.league_data = chalkboard_leagues
        load_dotenv()

    # def ui_multiplier(self, prob: float) -> float:
    #     """
    #     Exact Hermes logic for Chalkboard UI multiplier
    #     (scope undefined path — CS2 player props)
    #     """
    #     # calculateAdjustedProbability
    #     adj_p = prob + (prob * (1 - prob)) / 2
    #
    #     # fair odds
    #     odds = 1 / adj_p
    #
    #     # formatNumber
    #     return round((odds + 2.220446049250313e-16) * 100) / 100

    def _generate_payload(self, league_name: str, stat_list: list):
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

    def _extract_game_data(self, game_data, margins: dict):
        document_name = game_data.get("document", {}).get("name", "")

        # There were duplicates, so add this logic check. Will have to check if this affects other leagues in the future.
        if not document_name.endswith("guaranteed-2"):
            return None

        base_map = game_data.get("document", {}).get("fields", {})
        if base_map.get("isLive", {}).get("booleanValue"):
            return None

        player_map = base_map.get("player", {}).get("mapValue", {}).get("fields", {})
        raw_league = base_map.get("gameType", {}).get("stringValue")
        league = LEAGUES.get(raw_league.upper(), raw_league).upper()
        start_date = self.cache_time(base_map.get("displayScheduled", {}).get("stringValue"))

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
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([player_name, start_date])

        market_base = base_map.get("markets", {}).get("mapValue", {}).get("fields")

        stat_options = {
            "over": market_base.get("over", {}),
            "under": market_base.get("under", {})
        }

        if "nullValue" in stat_options.get("over") and "nullValue" in stat_options.get("under"):
            return None


        return PlayerData(
            player_name=player_name,
            league=league,
            start_date=start_date,
            team_data=TeamData(
                team_a=self.clean_and_normalize_name(team_a),
                team_b=self.clean_and_normalize_name(team_b),
                team_key=team_key,
                player_team=self.clean_and_normalize_name(player_team),
                team_a_abbreviation=team_a_abbreviation,
                team_b_abbreviation=team_b_abbreviation
            ),
            future=False,
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(stat.get("mapValue", {}).get("fields", {}).get("statisticName", {}).get("stringValue").lower(), stat.get("mapValue", {}).get("fields", {}).get("statisticName", {}).get("stringValue")),
                    line=stat.get("mapValue", {}).get("fields", {}).get("value", {}).get("doubleValue"),
                    bet_direction=direction,
                    regular_line=False,
                    optional_stats={
                        # "probabilities": stat.get("mapValue", {}).get("fields", {}).get("probabilities", {}).get("doubleValue"),
                        "odds": stat.get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue"),
                        "multiplier": self._calculate_ui(
                            margin=margin_value,
                            odds=float(stat.get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue", 0))
                        )
                    }
                )
                for direction, stat in stat_options.items()
                if stat.get("mapValue", {}).get("fields", {}).get("statisticName", {}).get("stringValue") is not None
            ],
            solo_game=False if all([team_a, team_b]) else True,
            combo=False,
            live=False
        )

    def _valid_return(self, returned_data: dict,  key_name: str) -> bool:
        """Validate returned data from Chalkboard API"""
        if not returned_data or not returned_data.get("success") or not returned_data.get(key_name):
            return False

        return True

    def _calculate_ui(self, margin: float, odds: float) -> float:
        """Calculate UI multiplier"""
        modified_margin = 1 + margin
        ui_value = odds / modified_margin
        return round(ui_value, 2)


    async def _get_margin_odds_cutoff(self, session: aiohttp.ClientSession, headers: dict) -> Dict[str, dict]:
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

    def stat_counter(self, player_data_dict):
        from collections import Counter
        count = Counter()
        for data in player_data_dict.values():
            for stat in data.stats:
                count[stat.stat_type] += 1

        for c in count:
            print(f"{c}: {int(int(count[c]) / 2)}")

    async def run_book(self):
        redis_client = RedisManager(db=5)
        access_token = await redis_client.get_auth_token("chalkboard_access_token")
        await redis_client.close()

        if not access_token:
            return

        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url"),
                    headers=headers,
                    method=self.book_data.method,
                    payload=self._generate_payload(league_name=league_name.lower(), stat_list=stat_list)
                )

                for league_name, stat_list in self.league_data.items()
            ]

            results = await asyncio.gather(*tasks)
            settings = await self._get_margin_odds_cutoff(session=session, headers=headers)

            merged_data = [result for result in results if result and result.get("success")]

            player_data_dict = {}

            for league in merged_data:
                for game in league.get("data", []):
                    player_data = self._extract_game_data(game_data=game, margins=settings.get("margins", {}))
                    if player_data:
                        player_key = (
                            player_data.player_name,
                            player_data.team_data.team_a,
                            player_data.team_data.team_b,
                            player_data.start_date,
                        )

                        if player_key in player_data_dict:
                            player_data_dict[player_key].stats.extend(player_data.stats)
                        else:
                            player_data_dict[player_key] = player_data

            # self.stat_counter(player_data_dict)

            chalkboard_data = list(player_data_dict.values())
            # ser = self.serialize_data(data=chalkboard_data)
            # self.create_json(data=ser, file_name="chalkboard_data.json")
            return await self._database_mapper(chalkboard_data)


if __name__ == "__main__":
    chalk = Chalkboard()
    asyncio.run(chalk.run_book())