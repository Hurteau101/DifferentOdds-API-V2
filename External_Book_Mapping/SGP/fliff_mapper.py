import asyncio
import itertools
import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

def get_static_mapping():
    return static_mapping_service.get()

class FliffMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="fliff", category="sgp", request_type=SportbookRequestType.ASYNC)

    def _extract_primary_conflict_keys(self, league_data: dict) -> set:
        return set(
            league.get("conflict_fkey")
            for league in league_data.get("x_slots", {}).get("active_prematch_conflicts", [])
        )

    async def _extract_secondary_conflict_keys(self, conflict_keys: set, session: aiohttp.ClientSession) -> dict:
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("main_url"),
                method=self.book_data.mapping.method,
                payload={
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

        internal_mapper = {
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
            }
        }

        results = await asyncio.gather(*tasks)

        mapping = get_static_mapping()
        stat_mapping = mapping.get("stats", {})

        con_keys = {}

        seen_fkeys = set()

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
                        fkey = proposal.get("proposal_fkey")
                        player_fkey = proposal.get("player_fkey")

                        if fkey in seen_fkeys:
                            continue

                        seen_fkeys.add(fkey)

                        found_mapping = internal_mapper.get(channel_id)

                        market_name = proposal.get("t_131_market_name")

                        if found_mapping:
                            market_name = found_mapping.get("stats", {}).get(market_name.lower(), market_name.lower())

                        if player_fkey:
                            market_name = f"player {market_name}"

                        mapped_market = stat_mapping.get(market_name.lower(), market_name.lower())
                        selection = proposal.get("t_141_selection_name", '').lower()
                        con_keys.setdefault(con_key, {}).setdefault(mapped_market, {}).setdefault(selection, fkey)

        return con_keys

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
        raw_league = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("main_url"),
            method=self.book_data.mapping.method,
            payload={
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
            return False


        conflict_keys = self._extract_primary_conflict_keys(league_data=raw_league)

        mapped_ids = await self._extract_secondary_conflict_keys(conflict_keys=conflict_keys, session=session)

        # stat_types = set(
        #     map_key
        #     for mapped_conflict in mapped_ids.values()
        #     for map_key in mapped_conflict.keys()
        # )


        if mapped_ids:
            await redis_instance.store_data(
                key_name="fliff_ids",
                data_to_store=mapped_ids,
                key_expiration=900
            )

            return True

        return False


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = FliffMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
