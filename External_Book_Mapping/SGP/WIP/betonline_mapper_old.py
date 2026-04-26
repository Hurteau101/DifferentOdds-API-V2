import asyncio
import itertools
import re
import time

import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import clean_structure
from Utils.request_caller import SportbookRequestType
from curl_cffi import AsyncSession as CurlAsyncSession

def get_static_mapping():
    return static_mapping_service.get()

class BetonlineMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="betonline", category="sgp", request_type=SportbookRequestType.SPOOF)

    async def _get_sports(self, session: CurlAsyncSession) -> set:
        raw_sports = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("sports_url"),
            method=self.book_data.mapping.method,
            headers=self.book_data.mapping.headers,
            parse_json=True
        )

        return set(
            sport.get("SportID")
            for sport in raw_sports.get("Sports", [])
        )

    async def _get_leagues_sports(self, session: CurlAsyncSession, sport_ids: set) -> list:
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

    async def _get_events(self, session: CurlAsyncSession, league_sport_ids: list) -> dict:
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

        ## We need EventID to help when we map the SGP Data.
        return {
            events.get("EventID"): events.get("SportCastFixtureId")
            for data in event_results
            if data
            for sports in data.get("Sports", [])
            for leagues in sports.get("Leagues", [])
            for events in leagues.get("Events", [])

        }


    async def _get_markets(self, session: CurlAsyncSession, fixture_ids: dict):
        market_results = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("market_labels_url"),
                    method="GET",
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    params={
                        "key": "0f833f77-d3e2-476b-8484-141fccb8d8de", # Publicly exposed key, no need to hide.
                        "culture": "en-GB",
                        "fixtureId": fxiture_id,
                        "returnFilters": True, # Ensure this is true, or we will need to call another endpoint to get the market data. True = include market data.
                    }
                )
                for fxiture_id in fixture_ids.values()
            ]
        )

        mapped_ids = {}

        # Prefix with sgp_ are the values, that the SGP engine needs. The market_name and selection are what we will use to map to the SGP values.
        # This is why we're storing similar values.

        for market, fixture_id in zip(market_results, fixture_ids.keys()):
            for payload in market.get("PayLoad", []):
                sgp_label = payload.get("UntranslatedLabel")
                market_name = payload.get("Label")

                for item in payload.get("Filter", {}).get("Items", []):

                    entity_id = item.get("EntityId")
                    sgp_selection = item.get("UntranslatedValue")
                    selection = item.get("Value")
                    cleaned_selection = re.sub(r'\s*\(.*?\)', '', clean_structure(selection)).strip()

                    nested_items = item.get("Items", {}) or {}
                    has_nested_items = isinstance(nested_items.get("Items", None), list)

                    if has_nested_items:
                        self.handle_nested_items(nested_items.get("Items", []), mapped_ids=mapped_ids, entity_id=entity_id,
                                                 fixture_id=fixture_id, market_name=market_name, sgp_label=sgp_label,
                                                 sgp_selection=sgp_selection, cleaned_selection=cleaned_selection)


                    mapped_ids.setdefault(fixture_id, {}).setdefault(market_name, {}).setdefault(cleaned_selection, {
                        "sgp_label": sgp_label,
                        "sgp_selection": sgp_selection,
                        "entity_id": entity_id,
                        "global_id": item.get("GlobalIdLong")
                    })

        return mapped_ids

    def handle_nested_items(self, items: list, mapped_ids: dict, entity_id: str, fixture_id: str, market_name: str, sgp_label: str, sgp_selection: str, cleaned_selection: str):
        for item in items:
            line = item.get("Value")











    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        sport_ids = await self._get_sports(session=session)
        league_sport_ids = await self._get_leagues_sports(session=session, sport_ids=sport_ids)
        fixture_ids = await self._get_events(session=session, league_sport_ids=league_sport_ids)
        markets = await self._get_markets(session=session, fixture_ids=fixture_ids)

        import json
        with open("betonline_mapped_ids.json", "w") as f:
            json.dump(markets, f, indent=4)

        # await redis_instance.store_data(
        #     key_name="bovada_ids",
        #     data_to_store=mapped_ids,
        #     key_expiration=900
        # )


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BetonlineMapper()
    async def main():
        async with CurlAsyncSession(impersonate="chrome120") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
