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

class BetwayMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="betway", category="sgp", request_type=SportbookRequestType.ASYNC)

    async def _get_categories(self, category_names: set, session: aiohttp.ClientSession) -> list:
        raw_categories = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("category_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "BrandId": 3,
                        "LanguageId": 25,
                        "ClientTypeId": 2,
                        "JurisdictionId": 2,
                        "ClientIntegratorId": 1,
                        "CategoryCName": category
                    }
                )

                for category in category_names
            ]
        )

        return [
            {
                "SubCategoryCName": sub.get("SubCategoryCName"),
                "CategoryCName": data.get("CategoryCName"),
                "GroupCName": group.get("GroupCName"),
            }

            for data in raw_categories
            if data.get("CategoryCName")
            for sub in data.get("SubCategories", [])
            for group in sub.get("Groups", [])
        ]

    async def _get_event_ids(self, session: aiohttp.ClientSession, categories: list):
        raw_ids = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("events_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "BrandId": 3,
                        "LanguageId": 25,
                        "ClientTypeId": 2,
                        "JurisdictionId": 2,
                        "ClientIntegratorId": 1,
                        "GroupCName": category.get("GroupCName"),
                        "CategoryCName": category.get("CategoryCName"),
                        "SubCategoryCName": category.get("SubCategoryCName")
                    }
                )

                for category in categories
            ]
        )

        events_ids = set()

        for data in raw_ids:
            for categories in data.get("Categories", []):
                events = set(categories.get("Events", []))
                events_ids.update(events)

        return events_ids


    async def _get_mappings(self, session: aiohttp.ClientSession, event_ids: set):
        async def process_mapping(event_id, semaphore: asyncio.Semaphore):
            async with semaphore:
                results = await self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("event_details"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "BrandId": 3,
                        "LanguageId": 25,
                        "ClientTypeId": 2,
                        "JurisdictionId": 2,
                        "ClientIntegratorId": 1,
                        "EventId": event_id,
                        "ScoreboardRequest": {
                            "IncidentRequest": {},
                            "ScoreboardType": 3
                        }
                    }
                )

                return results if results else {}


        semaphore = asyncio.Semaphore(20)
        tasks = [process_mapping(event_id, semaphore) for event_id in event_ids]
        results = await asyncio.gather(*tasks)

        mapping_data = {}

        mapping = get_static_mapping()
        stat_mapping = mapping.get("stats", {})

        for result in results:
            if not result:
                continue

            raw_event_name = result.get("Event", {}).get("EventName")
            if not raw_event_name:
                continue

            event_name = raw_event_name.replace("-", "vs").lower()
            event_bucket = mapping_data.setdefault(event_name, {})

            markets = result.get("Markets", [])

            for market in markets:
                raw_market_name = market.get("Title").lower().replace("alternate", "").strip()
                cleaned_market_name = stat_mapping.get(raw_market_name, raw_market_name).lower()
                market_bucket = event_bucket.setdefault(cleaned_market_name, {})

                selection_list = market.get("Headers", [])
                outcome_list = market.get("Outcomes", [])[0]

                if not selection_list or not outcome_list:
                    continue

                for selection, outcome in zip(selection_list, outcome_list):
                    handicap = market.get("Handicap", 0.00)
                    selection = selection.lower()

                    if handicap != 0.00:
                        selection = f"{selection} {handicap}"

                    selection_bucket = market_bucket.setdefault(selection, {})
                    selection_bucket.update({"outcome_id": outcome})





        import json
        with open("mapping_test.json", "w") as file:
            json.dump(mapping_data, file, indent=2)


    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        raw_categories = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("category_names"),
            method=self.book_data.mapping.method,
            headers=self.book_data.mapping.headers,
            payload={
                "BrandId": 3,
                "LanguageId": 25,
                "TerritoryId": 38,
                "TerritoryCode": "CA",
                "ClientTypeId": 2,
                "JurisdictionId": 2,
                "ClientIntegratorId": 1,
                "MenuIds": [
                    8
                ]
            }
        ) or {}

        category_names = set(
            menu.get("ClientLink", {}).get("ClientLinkValue")
            for menu in raw_categories.get("MenuData", {}).get("MenuItems", [])
        )

        if not category_names:
            create_sentry_message(
                tag_key="betway",
                tag_value="mapping_failure",
                message="No category names found",
                level="error"
            )

        categories = await self._get_categories(category_names, session)

        if not categories:
            create_sentry_message(
                tag_key="betway",
                tag_value="mapping_failure",
                message="No category details found",
                level="error"
            )

        event_ids = await self._get_event_ids(session, categories)

        if not event_ids:
            create_sentry_message(
                tag_key="betway",
                tag_value="mapping_failure",
                message="No event details found",
            )

        mapped_data = await self._get_mappings(session, event_ids)




if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BetwayMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())