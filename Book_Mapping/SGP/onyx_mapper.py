import asyncio

import aiohttp

from Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType
from Redis.redis_manager import RedisAsyncManager

class OnyxMapper(BaseMapper):
    def __init__(self):
        super().__init__(book_name="onyxodds", category="sgp", request_type=SportbookRequestType.ASYNC)

    async def _get_auth(self) -> str | None:
        redis = RedisAsyncManager(database=5)
        auth_token = await redis.get_data("onyx_auth_token")
        return auth_token

    async def _extract_game_ids(self, league_names: set, session: aiohttp.ClientSession, auth_token: str) -> set | None:
        if not auth_token or not league_names:
            return None

        # Not ASYNC Tasks due to potential rate limit and missing leagues.
        results = []
        for league in league_names:
            result = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("game_ids_url").format(league_name=league),
                method=self.book_data.mapping.method,
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            results.append(result)
            await asyncio.sleep(0.5)


        if not results:
            return None

        return set(
            game_values.get("ojId")
            for games in results
            for game_values in games.get("data", {}).values()
        )


    def _extract_mapped_ids(self, api_data: dict, game_id: str | int) -> dict:
        markets = api_data.get(game_id, {}).get("markets")
        if not markets:
            return {}

        mapped_ids = {}

        # Since we don't know the key values, we have to iterate through the nested dictionaries values.
        for section_1 in markets.values():
            if not section_1:
                continue

            for section_2_keys, section_2_values in section_1.items():
                if not section_2_keys or not section_2_values:
                    continue

                selection_id = section_2_values.get("id")
                if selection_id:
                    mapped_ids[selection_id] = {
                        "name": section_2_values.get("name"),
                        "market_name": section_2_values.get("marketName"),
                        "fixture_id": section_2_values.get("fixtureId"),
                        "semantic_id": section_2_values.get("semanticId"),
                    }

        return mapped_ids

    def _extract_league_names(self, raw_data: dict) -> set:
        return set(
            league_data.get("league")
            for league_data in raw_data.get("data", {}).values()
        )

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        auth_token = await self._get_auth()
        if not auth_token:
            create_sentry_message(
                tag_key="onyxodds",
                tag_value="no_auth",
                message="Couldn't find auth token in redis",
                level="error"
            )

            return

        league_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.mapping.url.get("league_url"),
            method=self.book_data.mapping.method,
            headers={
                "Authorization": f"Bearer {auth_token}"
            }
        )

        if not league_data:
            create_sentry_message(
                tag_key="onyxodds",
                tag_value="mapping_failure",
                message="No league data found during Onyx mapping.",
                level="error"
            )

            return

        leagues = self._extract_league_names(league_data)
        game_ids = await self._extract_game_ids(league_names=leagues, session=session, auth_token=auth_token)

        if not game_ids:
            create_sentry_message(
                tag_key="onyxodds",
                tag_value="mapping_failure",
                message="No game IDs found during Onyx mapping.",
                level="error"
            )

            return

        market_url_tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("market_url").format(game_id=game_id),
                method=self.book_data.mapping.method,
                headers={
                    "Authorization": f"Bearer {auth_token}"
                }
            )
            for game_id in game_ids
        ]

        market_url_results = await asyncio.gather(*market_url_tasks)

        if not market_url_results:
            create_sentry_message(
                tag_key="onyxodds",
                tag_value="mapping_failure",
                message="No market data found during Onyx mapping.",
                level="error"
            )

            return


        all_mapped_ids = {}

        for api_data, game_id in zip(market_url_results, game_ids):
            if api_data:
                mapped_ids = self._extract_mapped_ids(api_data, game_id)
                all_mapped_ids.update(mapped_ids)

        if all_mapped_ids:
            await redis_instance.store_data(
                key_name="onyx_ids",
                data_to_store=all_mapped_ids,
                key_expiration=self.default_key_expiration
            )