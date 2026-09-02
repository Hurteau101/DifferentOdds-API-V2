import asyncio
import re
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.mapper_base import MapperBase
from curl_cffi import AsyncSession as CurlAsyncSession
from Redis.redis_manager import RedisSyncManager

PLAYER_REGEX = re.compile(r"^(.*?)\s*-\s(.+?)\s*\([A-Za-z]{1,4}\)$")
MILESTONE_REGEX = re.compile(r"to get\s+(\d+)\s*\+\s*(.+)", re.IGNORECASE)
RAW_NAME_REGEX = re.compile(r"^\s*([^(]+?)\s*(?:\(|$)")

class BetwayMapper(MapperBase):
    ALLOWED_LEAGUES = ["ice-hockey", "basketball", "american-football", "baseball", "soccer", "ufc---martial-arts", "tennis"]

    def __init__(self):
        super().__init__(book_name="betway", category="sgp")

    async def _get_categories(self, category_names: set, session: CurlAsyncSession) -> list:
        raw_categories = await asyncio.gather(
            *[
                self.api_caller(
                    session=session,
                    url=self.book_data.mapping.url.get("category_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    default_headers=False,
                    json={
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

    async def _get_event_ids(self, session: CurlAsyncSession, categories: list):
        raw_ids = await asyncio.gather(
            *[
                self.api_caller(
                    session=session,
                    url=self.book_data.mapping.url.get("events_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    default_headers=False,
                    json={
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

    def _market_details(self, markets: list, stat_mapping: dict):
        """Map market details"""
        market_data = {}

        for market in markets:
            if not market.get("IsBetBuilderSupported", False):
                continue

            raw_market_name = market.get("Title")
            market_bucket = market_data.setdefault(market.get("Id"), {})

            if match := PLAYER_REGEX.match(raw_market_name):
                market_match_name = match.group(1)
                mapped_market = stat_mapping.get(market_match_name.lower(), market_match_name)

                market_bucket.update({
                    "market_name": f"Player {mapped_market}",
                    "player_name": match.group(2),
                })

            if milestone_match := MILESTONE_REGEX.search(raw_market_name):
                milestone_name = milestone_match.group(2)
                market_bucket.update({
                    "market_name": stat_mapping.get(milestone_name.lower(),milestone_name),
                    "side": "over",
                    "line": str(float(milestone_match.group(1)) - 0.5),
                })

            if not market_bucket:
                market_bucket.update({
                    "market_name": stat_mapping.get(raw_market_name.lower(), raw_market_name),
                })

        return market_data

    async def _get_mappings(self, session: CurlAsyncSession, event_ids: set):
        async def process_mapping(event_id, semaphore: asyncio.Semaphore):
            async with semaphore:
                results = await self.api_caller(
                    session=session,
                    url=self.book_data.mapping.url.get("event_details"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    default_headers=False,
                    json={
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

        mapping = self.static_mapping.get("static_mapping", {})
        stat_mapping = mapping.get("stats", {})

        espn_mapping_redis_instance = RedisSyncManager(database=8)
        espn_mapping = espn_mapping_redis_instance.get_data(key_name="espn_mapping")

        final_map = {}

        for result in results:
            if result.get("Errors", []):
                continue

            event_id = str(result.get("Event", {}).get("Id"))
            league = result.get("Event", {}).get("GroupName", '')

            market_map = self._market_details(result.get("Markets", []), stat_mapping=stat_mapping)

            for outcome in result.get("Outcomes", []):
                found_market_map = market_map.get(outcome.get("MarketId"))

                if not found_market_map:
                    continue

                found_market_map = dict(found_market_map)

                bet_name = outcome.get("BetName", '')
                current_line = found_market_map.get("line")

                # Player name in here.
                if current_line:
                    if raw_match := RAW_NAME_REGEX.match(bet_name):
                        old_market_name = found_market_map.get("market_name")

                        found_market_map.update({
                            "player_name": raw_match.group(1),
                            "market_name": f"Player {old_market_name}"
                        })
                else:
                    found_market_map.update({
                        "side": bet_name,
                        "line": outcome.get("HandicapDisplay")
                    })

                market_name = found_market_map.get("market_name", '')

                if market_name.lower() in ["point spread", "spread", "run line", "puck line"]:
                    found_abbrev = espn_mapping.get(league, {}).get(bet_name, {}).get("abbreviation", '')
                    if found_abbrev:
                        found_market_map["side"] = f"{found_abbrev} {found_market_map.get('line', 'N/A')}"
                        found_market_map['line'] = None

                found_market_map["market_name"] = self._special_mapping(mapping_name=market_name, league=league)

                values = list(found_market_map.values())
                mapping_key = self.build_prop_key(*values)

                final_map.setdefault(event_id, {})[mapping_key] = {
                    **found_market_map,
                    "outcome_id": outcome.get("Id"),
                    "league": league
                }

        return final_map

    async def check_categories(self, session: CurlAsyncSession):
        async def check_redis():
            return await self.redis_manager.get_data("betway_categories")

        has_cache = await check_redis()

        if has_cache:
            return has_cache

        raw_categories = await self.api_caller(
            session=session,
            url=self.book_data.mapping.url.get("category_names"),
            method=self.book_data.mapping.method,
            headers=self.book_data.mapping.headers,
            default_headers=False,
            json={
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

        categories = await self._get_categories(category_names, session)

        if not categories:
            return None

        await self.store_data(
            key_name="betway_categories",
            data_to_store=categories,
            expiration_time=3600  # 1 Hour
        )

        return categories

    async def run_mapper(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            categories = await self.check_categories(session)
            if not categories:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No categories found"
                )

                return False

            event_ids = await self._get_event_ids(session, categories)

            if not event_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No event IDs found"
                )
                return False

            mapping = await self._get_mappings(session, event_ids)

            if not mapping:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No mapping found"
                )

                return False

            await self.store_data(
                key_name=self.mapper_id_name,
                data_to_store=mapping,
                expiration_time=900
            )

            return True





if __name__ == "__main__":
    mapper = BetwayMapper()
    asyncio.run(mapper.run_mapper())
