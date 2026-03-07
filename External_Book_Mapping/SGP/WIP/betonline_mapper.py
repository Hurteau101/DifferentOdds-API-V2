import asyncio
import re
from collections import defaultdict
import aiohttp
from curl_cffi import AsyncSession

from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


### MOVE GET STATIC METHOD TO BASE CLASS AFTER TESTING FURTHER
def get_static_mapping():
    return static_mapping_service.get()


##### WORK ON FIXING AS ITS NOT FUNCTIONING PROPERLY FOR MAPPING. (_CREATING_MAPPING IS BROKEN)

class BetonlineMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="betonline", category="sgp", request_type=SportbookRequestType.SPOOF)

    async def _get_sports(self, session: AsyncSession) -> set:
        raw_sports = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("sports_url"),
            method=self.book_data.mapping.method,
            headers=self.book_data.mapping.headers,
            parse_json=True
        ) or {}

        return set(
            sport.get("SportID")
            for sport in raw_sports.get("Sports", [])
        )

    async def _get_leagues_sports(self, session: AsyncSession, sport_ids: set) -> list:
        league_results = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("leagues_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={"SportID": sport_id}
                )
                for sport_id in sport_ids
            ]
        )

        return [
            {
                "league_id": league.get("LeagueID"),
                "sport_id": sport.get("SportID"),
                "scheduled_text": league.get("ScheduleText")
            }

            for data in league_results
            if data
            for sport in data.get("Sports", [])
            for league in sport.get("Leagues", [])
        ]


    async def _get_events(self, session: AsyncSession, league_sport_ids: list) -> dict:
        event_results = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("events_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "SportID": ids.get("sport_id"),
                        "LeagueID": ids.get("league_id"),
                        "ScheduleText": ids.get("scheduled_text")
                    }
                )
                for ids in league_sport_ids
            ]
        )

        return {
            events.get("SportCastFixtureId"): {
                "event_name": " vs ".join(sorted([
                    events.get("TeamHome", {}).get("Name"),
                    events.get("TeamAway", {}).get("Name")
                ]
                ))

            }
            for data in event_results
            if data
            for sports in data.get("Sports", [])
            for leagues in sports.get("Leagues", [])
            for events in leagues.get("Events", [])

        }

    def extract_leaf_values(self, node):
        if not isinstance(node, dict):
            return []

        items = node.get("Items")

        # If no children → this is a leaf
        if not items or not items.get("Items"):
            return [node.get("Value")] if node.get("Value") else []

        values = []
        for child in items.get("Items", []):
            values.extend(self.extract_leaf_values(child))

        return values

    async def _create_mapping(self, session: AsyncSession, fixture_data: dict) -> dict:
        async def fetch_mapping(fixture_id: str):
            result = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("mapping_url"),
                method="GET",
                headers=self.book_data.mapping.headers,
                parse_json=True,
                params={
                    "key": "0f833f77-d3e2-476b-8484-141fccb8d8de",
                    "fixtureId": fixture_id,
                    "culture": "en-GB",
                    "returnFilters": True,
                }
            )
            return fixture_id, result

        mapping_results = await asyncio.gather(
            *[fetch_mapping(fid) for fid in fixture_data]
        )

        if not mapping_results:
            return {}

        # Load static stat mapping safely
        static_mapping = get_static_mapping() or {}
        stat_mapping = static_mapping.get("stats", {})

        event_mapping = defaultdict(dict)

        for fixture_id, result in mapping_results:
            if not result or result.get("Error"):
                continue

            event_info = fixture_data.get(fixture_id)
            if not event_info:
                continue

            event_name = event_info.get("event_name")
            if not event_name:
                continue

            event_bucket = event_mapping[event_name]

            for payload in result.get("PayLoad", []) or []:
                if not payload:
                    continue

                raw_stat_type = payload.get("Label")
                if not raw_stat_type:
                    continue

                cleaned_market_name = stat_mapping.get(
                    raw_stat_type.lower(),
                    raw_stat_type
                ).lower()

                market_bucket = event_bucket.setdefault(cleaned_market_name, {})

                for filter_node in payload.get("Filter", {}).get("Items", []) or []:
                    if not filter_node:
                        continue

                    selection = filter_node.get("Value")
                    if not selection:
                        continue

                    selection_lower = selection.lower()

                    # Extract deepest leaf values
                    lines = self.extract_leaf_values(filter_node)

                    if not lines:
                        continue

                    if len(lines) == 1 and lines[0].lower() == selection_lower:
                        market_bucket[selection_lower] = {
                            "untranslated_market_name": payload.get("UntranslatedLabel"),
                            "market_label_id": payload.get("LabelId"),
                            "fixture_id": fixture_id,
                        }
                    else:
                        selection_bucket = market_bucket.setdefault(selection_lower, {})

                        for line in lines:
                            if not line:
                                continue

                            combined_key = f"{selection_lower} {line}".strip()

                            selection_bucket[combined_key] = {
                                "untranslated_market_name": payload.get("UntranslatedLabel"),
                                "market_label_id": payload.get("LabelId"),
                                "fixture_id": fixture_id,
                            }

        import json
        print(json.dumps(event_mapping, indent=2))
        return dict(event_mapping)

    # async def _create_mapping(self, session: AsyncSession, fixture_data: dict) -> dict:
    #     async def fetch_mapping(fixture_id: str):
    #         result = await self.api_caller(
    #             book_name=self.book_data.name,
    #             session=session,
    #             url=self.book_data.mapping.url.get("mapping_url"),
    #             method="GET",
    #             headers=self.book_data.mapping.headers,
    #             parse_json=True,
    #             params={
    #                 "key": "0f833f77-d3e2-476b-8484-141fccb8d8de",
    #                 "fixtureId": fixture_id,
    #                 "culture": "en-GB",
    #                 "returnFilters": True,
    #             }
    #         )
    #         return fixture_id, result
    #
    #     mapping_results = await asyncio.gather(
    #         *[fetch_mapping(id) for id in fixture_data]
    #     )
    #
    #     if not mapping_results:
    #         return {}
    #
    #     mapping = get_static_mapping()
    #     stat_mapping = mapping.get("stats", {})
    #
    #     mapping = defaultdict(dict)
    #
    #     for fixture_id, result in mapping_results:
    #         if not result or result.get("Error"):
    #             continue
    #
    #         event_name = fixture_data.get(fixture_id).get("event_name")
    #
    #         event_bucket = mapping.setdefault(event_name, {})
    #
    #         for payload in result.get("PayLoad", []) or []:
    #             if not payload:
    #                 continue
    #
    #             raw_stat_type = payload.get("Label")
    #             cleaned_market_name = stat_mapping.get(raw_stat_type.lower(), raw_stat_type).lower()
    #
    #             market_bucket = event_bucket.setdefault(cleaned_market_name, {})
    #
    #             for filter_node in payload.get("Filter", {}).get("Items", []) or []:
    #                 if not filter_node:
    #                     continue
    #
    #                 selection = filter_node.get("Value")  # e.g. "Over"
    #                 if not selection:
    #                     continue
    #
    #                 lines = self.extract_leaf_values(filter_node)
    #                 lines = [line for line in lines if line.lower() != "game"]
    #
    #                 selection_bucket = market_bucket.setdefault(selection.lower(), {})
    #
    #                 for line in lines:
    #                     selection_bucket[line] = {
    #                         "untranslated_market_name": payload.get("UntranslatedLabel"),
    #                         "market_label_id": payload.get("LabelId"),
    #                         "fixture_id": fixture_id,
    #                     }
    #
    #             # for filter in payload.get("Filter", {}).get("Items", []):
    #             #     if not filter:
    #             #         continue
    #             #
    #             #     # if filter.get("Items"):
    #             #     #     print(fixture_id)
    #             #     #     additional_items = [
    #             #     #         item_2.get("Value")
    #             #     #         for item in filter.get("Items", {}).get("Items", [])
    #             #     #         for item_2 in item.get("Items", {}).get("Items", [])
    #             #     #     ]
    #             #     #
    #             #     #
    #             #     #     print(additional_items)
    #             #     #
    #             #     #
    #             #     # selection = filter.get("Value")
    #             #
    #             #     all_values = self.extract_values(filter_item)
    #             #
    #             #     # market_bucket[selection] = {
    #             #     #     "untranslated_market_name": payload.get("UntranslatedLabel"),
    #             #     #     "market_label_id": payload.get("LabelId"),
    #             #     #     "fixture_id": fixture_id,
    #             #     # }
    #
    #
    #     import json
    #     print(json.dumps(mapping, indent=2))






    async def run_scheduler(self, session: AsyncSession, redis_instance: RedisAsyncManager):
        sport_ids = await self._get_sports(session=session)
        if not sport_ids:
            create_sentry_message(
                tag_key="betonline",
                tag_value="mapping_failure",
                message="No sports found",
                level="error"
            )

        league_sport_ids = await self._get_leagues_sports(session=session, sport_ids=sport_ids)

        if not league_sport_ids:
            create_sentry_message(
                tag_key="betonline",
                tag_value="mapping_failure",
                message="No leagues found",
                level="error"
            )

        fixture_ids = await self._get_events(session=session, league_sport_ids=league_sport_ids)

        if not fixture_ids:
            create_sentry_message(
                tag_key="betonline",
                tag_value="mapping_failure",
                message="No events found",
                level="error"
            )

        mapping_data = await self._create_mapping(session=session, fixture_data=fixture_ids)













if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BetonlineMapper()
    async def main():
        async with AsyncSession(impersonate="chrome120") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
