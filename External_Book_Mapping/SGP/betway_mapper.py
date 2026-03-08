import asyncio
import re
import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


#### WILL NEED TO MAP MLB ####
#### WILL NEED TO MAP NFL/NCAAF ###

### Not Mapped Since not in SGP ###
### NHL
# 1st period total goals
# Team Total

### NBA
# 1st half total points

####################################

### MOVE GET STATIC METHOD TO BASE CLASS AFTER TESTING FURTHER
def get_static_mapping():
    return static_mapping_service.get()

# Detects player markets formatted like:
# "total points - malik monk (sac)"

# Captures:
# group(1) -> stat portion before the dash (e.g. "total points")
# group(2) -> player name (e.g. "malik monk")
PLAYER_REGEX = re.compile(r"^(.*?)\s*-\s(.+?)\s*\([A-Za-z]{1,4}\)$")


# Detects milestone markets like:
# "player to get 50+ points"
# "player to get 50+ points, assists and rebounds"

# Captures:
# group(1) -> milestone value before '+'
# group(2) -> stat text after '+'
MILESTONE_REGEX = re.compile(r"to get\s+(\d+)\s*\+\s*(.+)", re.IGNORECASE)

# Has a team in it between ( )
TEAM_REGEX = re.compile(r"\s*\([A-Za-z]{3,4}\)")


class BetwayMapper(BaseMapper):
    # ALLOWED_LEAGUES = ["ice-hockey", "basketball", "american-football", "baseball", "soccer", "ufc---martial-arts", "tennis"]
    ALLOWED_LEAGUES = ["soccer"]

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


    async def format_mapping(self, outcomes: list) -> dict:
        outcome_mapping = {}

        for outcome in outcomes:
            outcome_id = outcome["Id"]
            raw_market_name = outcome["BetName"].lower()
            handicap_display = outcome.get("HandicapDisplay")
            handicap_value = outcome.get("Handicap")

            market_name = raw_market_name

            if handicap_display:
                market_name = f"{raw_market_name} {handicap_value}"


            outcome_mapping[outcome_id] = {
                "market_name": market_name,
                "raw_market_name": raw_market_name,
                "handicap_display": handicap_display,
                "handicap_value": handicap_value,
                "market_id": outcome["MarketId"]
            }

        return outcome_mapping


    async def _detect_player(self, market_name: str, selection_name: str):
        match = PLAYER_REGEX.match(market_name)


        if match:
            market_name = match.group(1).replace("total", "").strip()
            market_name = f"player {market_name}"
            found_player = match.group(2).strip()
            selection_name = f"{found_player} {selection_name}"
        else:
            match = MILESTONE_REGEX.search(market_name)
            if match:
                str_line = match.group(1)
                market_name = match.group(2).strip()
                line = float(str_line) - 0.5
                clean_selection = TEAM_REGEX.sub("", selection_name)
                selection_name = f"{clean_selection} over {str(line)}"

        return {
            "market_name": market_name,
            "selection_name": selection_name,
        }

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

        mapping = get_static_mapping()
        stat_mapping = mapping.get("stats", {})

        mapping_data = {}

        for result in results:
            if result.get("Errors", []):
                continue

            event_id = str(result.get("Event", {}).get("Id"))
            event_bucket = {}

            home_team = result.get("Event", {}).get("HomeTeamName", {})
            away_team = result.get("Event", {}).get("AwayTeamName", {})

            outcome_mapping = await self.format_mapping(result.get("Outcomes", []))

            for market in result.get("Markets", []):
                if not market.get("IsBetBuilderSupported", False):
                    continue

                outcomes = market.get("Outcomes", [])
                if outcomes and isinstance(outcomes[0], list):
                    outcomes = [item for sublist in outcomes for item in sublist]


                for outcome in outcomes:
                    found_mapping = outcome_mapping.get(outcome)
                    if not found_mapping:
                        continue

                    selection_name = found_mapping.get("market_name")
                    market_name = market.get("Title").lower().replace("alternate", "").strip()

                    found = await self._detect_player(market_name, selection_name)

                    market_name = found.get("market_name")
                    selection_name = found.get("selection_name")

                    if "player" not in market_name and TEAM_REGEX.search(found_mapping.get("raw_market_name")):
                        market_name = f"player {market_name}"

                    if any(team in market_name for team in ["team a", "team b", "home team", "away team"]):
                        market_name = (
                            market_name.replace("team a", home_team)
                            .replace("team b", away_team)
                            .replace("home team", home_team)
                            .replace("away team", away_team)
                            .replace("full time", "")
                            .strip()
                        )

                    market_name = stat_mapping.get(market_name.replace("player", "").strip(), market_name).lower()

                    if "corner" in market_name:
                        print(market_name)

                    mapping_key = "_".join([market_name, selection_name]).replace(" ", "_").lower()


                    market_bucket = event_bucket.setdefault(mapping_key, {})
                    market_bucket.update({"OutcomeId": outcome})

            if event_bucket:
                mapping_data[event_id] = event_bucket


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
        if not mapping:
            create_sentry_message(
                tag_key="betway",
                tag_value="mapping_failure",
                message="No mapping details found",
                level="error"
            )

            return

        with open("betway_mapping.json", "w") as f:
            import json
            json.dump(mapping, f, indent=2)

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