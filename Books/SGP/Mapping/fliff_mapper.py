import asyncio
import itertools
import re
from Books.Bases.mapper_base import MapperBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from curl_cffi import AsyncSession as CurlAsyncSession
from Redis.redis_manager import RedisSyncManager

LINE_DIRECTION = re.compile(r"(Over|Under)\s*(\d+(?:\.\d+)?)")
MILESTONE_REGEX = re.compile(r"play\w*\s+to\s+.*?(?:(\d+)\s*(?:\+|or more)|\ban?\b)\s+(.+)", re.IGNORECASE)


class FliffMapper(MapperBase):
    INTERNAL_MAPPER = {
        481: {
            "league": "NHL",
            "stats": {
                "total score": "total goals",
                "1st period total score": "1st period total goals",
            }
        },
        441: {
            "league": "MLB",
            "stats": {
                "total score": "total runs",
            }
        },
        451:{
            "league": "NFL",
        },
        452: {
            "league": "NCAAF"
        }
    }
    def __init__(self):
        super().__init__(book_name="fliff", category="sgp")
        self.mapping = self.static_mapping.get("static_mapping", {})

    def _extract_primary_conflict_keys(self, league_data: dict) -> set:
        return set(
            league.get("conflict_fkey")
            for league in league_data.get("x_slots", {}).get("active_prematch_conflicts", [])
        )

    def _extract_milestone(self, market_name: str, player_name: str, bucket: dict, fkey: str, channel_id: int):
        has_milestone = MILESTONE_REGEX.search(market_name)
        if has_milestone:
            milestone_value = has_milestone.group(1)

            if milestone_value:

                modified_market_name = self.INTERNAL_MAPPER.get(channel_id, {}).get("stats", {}).get(
                    market_name.lower(), market_name)

                modified_market_name = self.mapping.get(modified_market_name.lower(), modified_market_name)

                prop_key = self.build_prop_key(
                    stat=f"player {modified_market_name}",
                    side="over",
                    line=str(float(milestone_value) - 0.5) if milestone_value else str(0.5),
                    player=player_name
                )

                bucket.setdefault(prop_key, {
                    "id": fkey,
                    "milestone": True
                })


    def _has_line_direction(self, name: str, market_name: str, player_name: str, bucket: dict, fkey: str, channel_id: int, passed_in_direction=None) -> bool:
        found_line_direction = LINE_DIRECTION.search(name)
        if found_line_direction:
            modified_market_name = self.INTERNAL_MAPPER.get(channel_id, {}).get("stats", {}).get(market_name.lower(), market_name)
            modified_market_name = self.mapping.get(modified_market_name.lower(), modified_market_name)
            direction, line = found_line_direction.group(1), str(found_line_direction.group(2))

            if passed_in_direction:
                direction = passed_in_direction

            prop_key = self.build_prop_key(
                stat=f"player {modified_market_name}" if player_name else modified_market_name,
                side=direction,
                line=line,
                player=player_name
            )
            bucket.update({prop_key: {
                "id": fkey,
            }})

            return True

        return False

    async def _extract_secondary_conflict_keys(self, conflict_keys: set, session: CurlAsyncSession) -> dict:
        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("main_url"),
                method=self.book_data.mapping.method,
                json={
                      "header": {
                        "device_x_id": "web.cc38c7c9aa44db6bc754e152d881a20b",
                        "app_x_version": "5.0.27.245",
                        "app_install_token": "1s5evaC6BM",
                        "auth_token": "",
                        "conn_id": 8,
                        "platform": "prod",
                        "usa_state_code": "",
                        "usa_state_code_source": "ipOrigin=radar|regionCode=AB|meta=successGetRegionCode|geocodeOrigin=radar|regionCode=AB|meta=successGetRegionCode",
                        "country_code": "CA"
                      },
                      "invocation": {
                        "request": {
                          "__object_class_name": "FCM__Public_Feed_Sync__Request",
                          "subfeed_meta": {
                            "packed_subfeed_revisions": [

                            ],
                            "focused_channel_id": 441,
                            "focused_conflict_fkey": conflict_key,
                            "focused_player_fkey": "",
                            "focused_ticket_conflict_fkeys": [],
                            "focused_ticket_proposal_fkeys": [],
                            "focused_ticket_data": []
                          },
                          "code": 3061
                        }
                      },
                      "x_invocations": None,
                      "x_sb_meta": {
                        "sb_config_version": 9251,
                        "sb_user_profile_version": -1,
                        "sb_user_profile_meta": None
                      }
                }
            )

            for conflict_key in list(conflict_keys)

        ]

        results = await asyncio.gather(*tasks)

        con_keys = {}

        seen_fkeys = set()

        espn_mapping_redis_instance = RedisSyncManager(database=8)
        espn_mapping = espn_mapping_redis_instance.get_data(key_name="espn_mapping") or {}

        for result in results:
            if not result:
                continue
            for feed in result.get("x_slots", {}).get("prematch_subfeeds_updates", []):
                channel_id = feed.get("channel_id")

                for market in feed.get("market_updates", []):
                    con_key = market.get("conflict_fkey")

                    proposals = list(itertools.chain.from_iterable(
                        group.get("proposals", []) for group in market.get("groups", [])
                    ))

                    for proposal in proposals:
                        if proposal.get("parlays_not_allowed", 0) == 2:
                            continue

                        fkey = proposal.get("proposal_fkey")
                        player_fkey = proposal.get("player_fkey")

                        if fkey in seen_fkeys:
                            continue

                        seen_fkeys.add(fkey)

                        market_name = proposal.get("t_131_market_name")

                        bucket = con_keys.setdefault(con_key, {})
                        raw_selection_name = proposal.get("t_141_selection_name")

                        # Player Mapping
                        if player_fkey or "player to" in market_name.lower():
                            player_name = raw_selection_name.replace(proposal.get("t_151_cell_text_1"), '')
                            raw_direction = proposal.get("t_151_cell_text_1")

                            has_line_direction = self._has_line_direction(name=raw_direction, market_name=market_name, player_name=player_name, bucket=bucket, fkey=fkey, channel_id=channel_id)

                            if not has_line_direction:
                                self._extract_milestone(market_name=market_name, player_name=raw_selection_name, bucket=bucket, fkey=fkey, channel_id=channel_id)

                        # Game Mapping
                        else:
                            event_info = proposal.get("t_121_event_info")
                            teams = event_info.split(" vs ")

                            if not event_info:
                                continue

                            direction = next((team for team in teams if team.lower() in market_name.lower()), '')
                            new_market_name = " ".join(market_name.lower().replace(direction.lower(), "").split()) if direction else market_name

                            if not new_market_name:
                                continue

                            # Game Mappings - Totals, team totals, etc.
                            has_line_direction = self._has_line_direction(name=raw_selection_name, market_name=new_market_name, player_name=None, bucket=bucket, fkey=fkey,
                                                     channel_id=channel_id, passed_in_direction=direction)

                            # Alternate game mapping - things like moneyline, spread, etc.
                            if not has_line_direction:
                                line = proposal.get("t_151_cell_text_1")
                                direction = next((team for team in teams if team.lower() in raw_selection_name.lower()), None)

                                modified_market_name = self.INTERNAL_MAPPER.get(channel_id, {}).get("stats", {}).get(
                                    market_name.lower(), market_name)
                                modified_market_name = self.mapping.get(modified_market_name.lower(),
                                                                        modified_market_name)

                                abbreviation = direction[0:3] if direction else None

                                if modified_market_name.lower() in ["spread", "run line", "puck line", "point spread"]:
                                    direction = abbreviation

                                if modified_market_name.lower()  == "moneyline" and abbreviation:
                                    league = self.INTERNAL_MAPPER.get(channel_id, {}).get("league")
                                    found_league = espn_mapping.get(league, {})
                                    if found_league:
                                        direction = next((
                                            team_data.get("team_name")
                                            for team_data in found_league.values()
                                            if team_data.get("abbreviation").upper() == abbreviation.upper()
                                        ), direction)

                                prop_key = self.build_prop_key(
                                    stat=modified_market_name,
                                    side=direction,
                                    line=str(line) if line else None,
                                    player=None
                                )

                                bucket.setdefault(prop_key, {
                                    "id": fkey,
                                })

        return con_keys

    async def run_mapper(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            raw_league = await self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("main_url"),
                method=self.book_data.mapping.method,
                json={
                    "header": {
                        "device_x_id": "web.cc38c7c9aa44db6bc754e152d881a20b",
                        "app_x_version": "5.0.27.245",
                        "app_install_token": "1s5evaC6BM",
                        "auth_token": "",
                        "conn_id": 2,
                        "usa_state_code_source": "ipOrigin=radar|regionCode=|meta=|geocodeOrigin=radar|regionCode=|meta="
                    },
                    "invocation": {
                        "request": {
                            "__object_class_name": "FCM__Public_Feed_Sync__Request",
                            "code": 3054,
                            "subfeed_meta": {
                                "packed_subfeed_revisions": []
                            }
                        }
                    },
                    "x_invocations": None,
                    "x_sb_meta": {
                        "sb_config_version": 9251,
                        "sb_user_profile_version": -1,
                        "sb_user_profile_meta": None
                    }
                }
            )

            if not raw_league:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No raw leagues found"
                )

                return False

            conflict_keys = self._extract_primary_conflict_keys(league_data=raw_league)

            mapped_ids = await self._extract_secondary_conflict_keys(conflict_keys=conflict_keys, session=session)

            if not mapped_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No mapped ids found"
                )

                return False

            await self.store_data(
                key_name=self.mapper_id_name,
                data_to_store=mapped_ids,
                expiration_time=900
            )

            return True


if __name__ == "__main__":
    fliff = FliffMapper()
    asyncio.run(fliff.run_mapper())
