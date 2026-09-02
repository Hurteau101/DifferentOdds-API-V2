import asyncio
from dotenv import load_dotenv
from loguru import logger
from Books.Bases.mapper_base import MapperBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes


class OnyxMapper(MapperBase):
    load_dotenv()
    def __init__(self):
        super().__init__(book_name="onyx odds", category="sgp")

    async def _extract_game_ids(self, league_names: set, auth_token: str) -> set | None:
        if not auth_token or not league_names:
            return None

        # Not ASYNC Tasks due to potential rate limit and missing leagues.
        results = []
        for league in league_names:
            result = await self.api_caller(
                use_proxy=True,
                url=self.book_data.mapping.url.get("game_ids_url").format(league_name=league),
                method=self.book_data.mapping.method,
                headers={**self.book_data.mapping.headers,"Authorization": f"Bearer {auth_token}"}
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
        markets = api_data.get("data", {}).get(game_id, {}).get("markets")

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

    async def _fetch_market(self, semaphore: asyncio.Semaphore, game_id, auth_token: str):
        async with semaphore:
            return await self.api_caller(
                use_proxy=True,
                url=self.book_data.mapping.url.get("market_url").format(game_id=game_id),
                method=self.book_data.mapping.method,
                headers={
                    **self.book_data.mapping.headers,
                    "Authorization": f"Bearer {auth_token}"
                }
            )

    async def run_mapper(self) -> bool:
        auth_token = await self.redis_auth_manager.get_data("onyx_auth")
        
        if not auth_token:
            logger.error("No auth token found.")
            return False

        league_data = await self.api_caller(
            use_proxy=True,
            url=self.book_data.mapping.url.get("league_url"),
            method=self.book_data.mapping.method,
            headers={
                **self.book_data.mapping.headers,
                "Authorization": f"Bearer {auth_token}"
            }
        )

        if not league_data:
            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.MAPPING,
                error_message="No league data found"
            )

            return False

        leagues = self._extract_league_names(league_data)
        game_ids = await self._extract_game_ids(league_names=leagues, auth_token=auth_token)

        if not game_ids:
            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.MAPPING,
                error_message="No game IDs found"
            )

            return False

        semaphore = asyncio.Semaphore(50)

        market_url_tasks = [
            self._fetch_market(semaphore, game_id, auth_token)
            for game_id in game_ids
        ]

        market_url_results = await asyncio.gather(*market_url_tasks)


        if not market_url_results:
            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.MAPPING,
                error_message="No market urls found"
            )

            return False


        all_mapped_ids = {}

        for api_data, game_id in zip(market_url_results, game_ids):
            if api_data:
                mapped_ids = self._extract_mapped_ids(api_data, game_id)
                all_mapped_ids.update(mapped_ids)


        if not all_mapped_ids:
            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.MAPPING,
                error_message="No mapping found"
            )

            return False

        await self.store_data(
            key_name=self.mapper_id_name,
            data_to_store=all_mapped_ids,
        )

        return True



if __name__ == "__main__":
    onyx_mapper = OnyxMapper()
    asyncio.run(onyx_mapper.run_mapper())