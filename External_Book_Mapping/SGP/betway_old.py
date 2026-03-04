import asyncio
import re
import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


### MOVE GET STATIC METHOD TO BASE CLASS AFTER TESTING FURTHER
def get_static_mapping():
    return static_mapping_service.get()


class BetwayMapper(BaseMapper):
    ALLOWED_LEAGUES = ["ice-hockey", "basketball", "american-football", "baseball"]

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

    async def is_nested_list(self, element_to_check):
        try:
            next(x for x in element_to_check if isinstance(x, list))
        except StopIteration:
            return False

        return True

    async def remove_team_name(self, player_name: str):
        return re.sub(r"\s*\([a-zA-Z]{3,4}\)", "", player_name).strip()

    async def _get_mappings(self, session: aiohttp.ClientSession, event_ids: set):
        # event_ids = [16434743]

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

        mapping = get_static_mapping()
        stat_mapping = mapping.get("stats", {})

        mapping_data = {}

        for result in results:
            outcome_mapping = {
                outcome.get("Id"): {
                    "market_name": outcome.get("BetName").lower(),
                    "spread_display": outcome.get("HandicapDisplay")
                }
                for outcome in result.get("Outcomes", [])
            }

            raw_event_name = result.get("Event", {}).get("EventName")

            if not raw_event_name:
                continue

            split_event_name = raw_event_name.split("-")
            event_name = " vs ".join(sorted(split_event_name)).lower().strip()
            event_bucket = mapping_data.setdefault(event_name, {})


            for market in result.get("Markets", []):
                outcomes = market.get("Outcomes", [])
                if await self.is_nested_list(outcomes):
                    outcomes = outcomes[0]

                for outcome in outcomes:
                    found_mapping = outcome_mapping.get(outcome)
                    if not found_mapping:
                        continue

                    selection_name = found_mapping.get("market_name")
                    spread_display = found_mapping.get("spread_display")
                    market_name = market.get("Title").lower().replace("alternate", "").strip()
                    handicap = market.get("Handicap", 0.00)

                    if selection_name == "yes":
                        selection_name = "over 0.5"
                    elif selection_name == "no":
                        selection_name = "under 0.5"


                    if "spread" in market_name:
                        selection_name = f"{selection_name} {spread_display}"

                    if selection_name in ["over", "under"]:
                        if handicap != 0.00:
                            selection_name = f"{selection_name} {handicap}"

                    # Check if the market name contains a team abbreviation like (phx), (lal), etc.
                    if re.search(r"\([a-zA-Z]{3,4}\)", market_name):
                        player_part = market_name.split("-")[-1].strip()

                        # Get the player name portion.
                        player_name = await self.remove_team_name(player_part)
                        selection_name = f"{player_name} {selection_name}"

                        if market_name == "total points":
                            market_name = "player points"
                        else:
                            market_name = f'player {market_name.split("-")[0].strip()}'

                    if "player to get" in market_name:
                        match = re.search(r"(\d+)\+", market_name)
                        if match:
                            raw_number = int(match.group(1))
                            number = float(raw_number - 0.5)
                            modified_market_name = market_name.split("+")[-1].strip()
                            market_name = f"player total {modified_market_name}"
                            selection_name = f"over {await self.remove_team_name(selection_name)} {number}"


                    cleaned_market_name = stat_mapping.get(market_name, market_name).lower()
                    market_bucket = event_bucket.setdefault(cleaned_market_name, {})
                    selection_bucket = market_bucket.setdefault(selection_name, {})
                    selection_bucket.update({"outcome_id": outcome})

        return mapping_data


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
            if menu.get("ClientLink", {}).get("ClientLinkValue") in self.ALLOWED_LEAGUES
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

        mapping = await self._get_mappings(session, event_ids)

        if mapping:
            await redis_instance.store_data(
                key_name="betway_mapped_ids",
                data_to_store=mapping,
                key_expiration=600
            )

    ### Add to APScheduler if success

if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BetwayMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())