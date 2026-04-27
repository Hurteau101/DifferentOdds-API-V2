# TODO:
# 1. Get League & Sport IDs - Call endpoint
# 2. Get Game IDs - Call endpoint
# 3. Get Mapping Names - Per League - Call Endpoint
# 4. Call Market Endpoint for each mapping name.



### Mapping Conditions ###
# Host - bv2-us.digitalsportstech.com
# Common Path /api/

## Remove `aca`

# 1. `gfm` - /sgmMarkets/gfm/grouped [SB, GameID]
# 2. 'gameprops' - /game-props/gamesByGp [SB, GameID]
# 3. Market starts with first | `field` - /custom-markets/gamesByField [SB, GameID, Field (Stat name in array - Remove () and any content inside of it.)]
# 4. Market has () in array - /dfm/marketsBy[insert whatever is in () ex. exact] [SB, GameID, Statistic (Stat name in array - Remove () and any content inside of it.)]
# 5. Market is Titled Case - /dfm/gamesBySs [SB, GameID, Statistic (Stat name in array - Remove () and any content inside of it.)]
# 6. Lowercase or else everything else - /custom-markets/marketBy[insert whatever key name is] - [SB, GameID, Special (Stat name in array - Remove () and any content inside of it.)]
###########################


import asyncio
import itertools
import re
import time
import json
import aiohttp
from celery.signals import task_retry

from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import clean_structure
from Utils.request_caller import SportbookRequestType

def get_static_mapping():
    return static_mapping_service.get()

class PropBuilderMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="prop_builder", category="sgp", request_type=SportbookRequestType.ASYNC)


    async def _get_league_sport_ids(self, session: aiohttp.ClientSession) -> dict:
        raw_sports = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            headers=self.book_data.headers,
            url=self.book_data.mapping.url.get('league_url'),
            method=self.book_data.mapping.method,
            params={
                "sb": "betus",
                "user": "null",
            }
        ) or {}


        return {
            sport.get("name"): sport.get("sport")
            for sport in raw_sports
            if sport.get("name")
        }

    async def _get_events(self, session: aiohttp.ClientSession, sport_leagues: dict):
        tasks = await asyncio.gather(
            *[
               self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    headers=self.book_data.headers,
                    url=self.book_data.mapping.url.get('events_url'),
                    method=self.book_data.mapping.method,
                    params={
                        "sb": "betus",
                        "league": league,
                        "sport": sport
                    }
               )

                for league, sport in sport_leagues.items()
            ]
        )

        # Has teams here if needed.
        return {
            provider.get("id"): {
                "league": event_task.get("league"),
                "sport": event_task.get("sport"),
                "date": event_task.get("date"),
            }
            for task in tasks
            for event_task in task
            if event_task.get("isActive", False) and not event_task.get("isFinal", True)
            for provider in event_task.get("providers", [])
        }

    async def _get_builder_mapping(self, session: aiohttp.ClientSession, sport_leagues: dict):
        # leagues = {league for league in sport_leagues.keys()}
        raw_mapping = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    headers=self.book_data.headers,
                    url=self.book_data.mapping.url.get('mapping_url'),
                    method=self.book_data.mapping.method,
                    params={
                        "sb": "betus",
                        "league": league,
                    }
                )

                for league in sport_leagues.keys()
            ]
        )

        return {
            league: {
                market: values
                for market, values in mapping.items()
                if values
            }
            for league, mapping in zip(sport_leagues.keys(), raw_mapping)
        }

    async def build_caller(self, sports_mapping: dict, event_data: dict):
        build_mapper = {}

        for event_id, event_info in event_data.keys():
            found_mapping = sports_mapping.get(event_info.get("league"), {})

            if not found_mapping:
                continue

           ### DO LOGIC TO BUILD EVERYTHING NOW.










    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
        sport_league_names = await self._get_league_sport_ids(session=session)
        sport_mapping = await self._get_builder_mapping(session=session, sport_leagues=sport_league_names)

        # with open("league_sport_ids.json", "w") as file:
        #     json.dump(sport_league_names, file, indent=2)
        #
        # event_data = await self._get_events(session=session, sport_leagues=sport_league_names)
        #
        # with open("event_data.json", "w") as file:
        #     json.dump(event_data, file, indent=2)








        # await redis_instance.store_data(
        #     key_name="bovada_ids",
        #     data_to_store=mapped_ids,
        #     key_expiration=900
        # )


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = PropBuilderMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
