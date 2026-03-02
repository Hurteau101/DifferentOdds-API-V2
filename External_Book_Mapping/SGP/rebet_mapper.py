import asyncio
import re
from collections import defaultdict
import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


### MOVE GET STATIC METHOD TO BASE CLASS AFTER TESTING FURTHER
def get_static_mapping():
    return static_mapping_service.get()



class RebetMapper(BaseMapper):

    def __init__(self):
        super().__init__(book_name="rebet", category="sgp", request_type=SportbookRequestType.ASYNC)

    async def _get_events(self, session: aiohttp.ClientSession, league_ids: set) -> set:
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("games_url"),
                method=self.book_data.mapping.method,
                headers=self.book_data.mapping.headers,
                params={
                    "tournament_id": league_id,
                    "game_type": 1
                },
            ) or []

            for league_id in league_ids
        ]

        raw_events = await asyncio.gather(*tasks)

        return set(
            data.get("event_id")
            for game in raw_events
            if game
            for data in game.get("data", {}).get("events", [])
            if data.get("event_id")
        )


    async def _extract_mapping(self, session: aiohttp.ClientSession, event_ids: set) -> dict:
        mapping = get_static_mapping()
        stat_mapping = mapping.get("stats", {})

        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("event_url").format(event_id=event_id),
                method=self.book_data.mapping.method,
                headers=self.book_data.mapping.headers,
                params={
                    "market_configuration_type": "PREMATCH",
                }
            ) or []

            for event_id in event_ids
        ]

        raw_mapping = await asyncio.gather(*tasks)

        mapped_data = defaultdict(lambda: defaultdict(dict))

        for mapping in raw_mapping:
            if mapping:
                teams = [
                    competitor.get("name")
                    for competitor in mapping.get("data", {}).get("competitors", {}).get("competitor")
                ]

                event_name = " vs ".join(sorted([team.lower() for team in teams]))

                for market in mapping.get("data", {}).get("odds", {}).get("market", []):
                    market_name = market.get("name")
                    cleaned_market_name = re.sub(r"\(incl\.?.*$", "", market_name, flags=re.IGNORECASE).rstrip()
                    cleaned_market_name = stat_mapping.get(cleaned_market_name.lower(), cleaned_market_name).lower()

                    market_dict = mapped_data[event_name][cleaned_market_name]

                    for outcome in market.get("outcome", []):
                        outcome_name = outcome.get("name").lower()

                        market_dict[outcome_name] = {
                            "outcome_id": outcome.get("id"),
                            "market_id": market.get("id"),
                            "specifier": market.get("specifiers"),
                            "event_id": market.get("event_id"),
                        }


                        # outcome_name = outcome.get("name").lower()
                        # market_dict[outcome_name] = outcome.get("id")

                    # market_dict.update({
                    #     "market_id": market.get("id"),
                    #     "specifier": market.get("specifiers"),
                    #     "event_id": market.get("event_id"),
                    # })
                    #
                    # for outcome in market.get("outcome", []):
                    #     outcome_name = outcome.get("name").lower()
                    #     market_dict[outcome_name] = outcome.get("id")

        return mapped_data


    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        raw_events = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("leagues_url"),
            method=self.book_data.mapping.method,
            headers=self.book_data.mapping.headers
        ) or []

        league_ids = set(
            league.get("id")
            for data in raw_events.get("data", {}).get("sports", [])
            for country in data.get("countries", [])
            for league in country.get("leagues", [])
            )

        if not league_ids:
            create_sentry_message(
                tag_key="rebet",
                tag_value="mapping_failure",
                message="No leagues found",
                level="error"
            )

        event_ids = await self._get_events(session=session, league_ids=league_ids)

        if not event_ids:
            create_sentry_message(
                tag_key="rebet",
                tag_value="mapping_failure",
                message="No events found",
                level="error"
            )

        mapped_ids = await self._extract_mapping(session=session, event_ids=event_ids)

        import json
        with open("rebet_mapping.json", "w") as f:
            json.dump(mapped_ids, f, indent=2)

        if not mapped_ids:
            create_sentry_message(
                tag_key="rebet",
                tag_value="mapping_failure",
                message="No mapped IDs were extracted from Rebet mapping.",
                level="error"
            )


        await redis_instance.store_data(
            key_name="rebet_ids",
            data_to_store=mapped_ids,
            key_expiration=self.default_key_expiration
        )


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = RebetMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())