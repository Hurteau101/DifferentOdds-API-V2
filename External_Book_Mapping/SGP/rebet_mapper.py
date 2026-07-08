


### Main Things ###
# 1. Dictionary key will be:
#   - Event Name (Team vs Team)
#   - Date
#   - League
###################

### Mapping API ###
# 1. Call League Endpoint: ✅
#  - Get Sport ID
#  - Get League ID

# 2. Call Event List Endpoint [Sport ID, League ID]: ✅
# - Get Event ID


# 3. Call Market Endpoint [Event ID]
###############

### Actual Mapping ###
# - Can get teams from competitors array.
# - Store `name` in set, so no duplicates.
# - `name` key can be used for the market name [Inside of market array]
# - tab_name starts with 'player' - Handle Cases
# - Ensure `is_sgp_available` is true for the market
# - `name` in outcome array is the selection.


# Player
# - Check card type for player_milestone. Handle those cases. Other sie would be over_under
# - Player names are backwards.

########################

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


class RebetMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="rebet", category="sgp", request_type=SportbookRequestType.ASYNC)


    async def _get_league_sport_ids(self, session: aiohttp.ClientSession):
        raw_sport_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            headers=self.book_data.headers,
            url=self.book_data.mapping.url.get('leagues_url'),
            method=self.book_data.mapping.method,
        )

        return {
            league.get("id"): sport.get("id")
            for sport in raw_sport_data.get("data", {}).get("sports", [])
            for country in sport.get("countries", [])
            if country.get("name") == "USA" # Should filter to more of the main sports (MLB, NHL, NCAA, etc)
            for league in country.get("leagues", [])
        }

    async def _get_events(self, session: aiohttp.ClientSession, sport_league_ids: dict):
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                headers=self.book_data.headers,
                url=self.book_data.mapping.url.get('events_url'),
                method=self.book_data.mapping.method,
                params={
                    "tab": "MKT",
                    "sport_id": sport_id,
                    "item_id": "GAMES",
                    "league_id": league_id
                }
            )
            for league_id, sport_id in sport_league_ids.items()
        ]

        results = await asyncio.gather(*tasks)

        return {
            event.get("id")
            for result in results
            for event in result.get("data", {}).get("events", [])
        }

    async def _get_markets(self, session: aiohttp.ClientSession, event_ids: set):
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                headers=self.book_data.headers,
                url=self.book_data.mapping.url.get('market_urls').format(event_id=event_id),
                method=self.book_data.mapping.method,
                params={
                    "format_tabs": "true",
                    "event_type": "PREMATCH",
                    "include_players_tab": "true",
                }
            )
            for event_id in event_ids
        ]

        results = await asyncio.gather(*tasks)

        import json
        with open("rebet_markets.json", "w") as f:
            json.dump(results, f, indent=4)



    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
        league_ids = await self._get_league_sport_ids(session=session)
        print(league_ids)
        event_ids = await self._get_events(session=session, sport_league_ids=league_ids)
        print(event_ids)
        market_data = await self._get_markets(session=session, event_ids=event_ids)



        # await redis_instance.store_data(
        #     key_name="bovada_ids",
        #     data_to_store=mapped_ids,
        #     key_expiration=900
        # )


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = RebetMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
