import asyncio
import aiohttp
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_mapper_base import SGPMapperBase


class Onyx_Mapper(SGPMapperBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="onyx", log_directory="SGP Mapper Logs",
                         log_name="onyx_mapper.log")

    async def _get_auth(self):
        redis = RedisManager(db=5)
        auth_token = await redis.get_auth_token("onyx_auth_token")
        await redis.close()
        return auth_token

    async def _extract_game_ids(self, league_names, session, auth_token):
        if not auth_token or not league_names:
            return None

        # Not ASYNC Tasks due to potential rate limit and missing leagues.
        results = []
        for league in league_names:
            result = await self.api_caller(
                session=session,
                url=self.book_data.url.get("game_ids_url").format(league_name=league),
                method=self.book_data.method,
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


    def _extract_mapped_ids(self, api_data, game_id):
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

    def _extract_league_names(self, raw_data):
        return set(
            league_data.get("league")
            for league_data in raw_data.get("data", {}).values()
        )

    async def run_book(self):
        redis = RedisManager(db=self.redis_db)
        auth_token = await self._get_auth()
        if not auth_token:
            self.file_logger.log(
                sportsbook="onyx",
                message="No auth token found in Redis.",
            )

            return
        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_url"),
                method=self.book_data.method,
                headers={
                    "Authorization": f"Bearer {auth_token}"
                }
            )

            api_data = self.check_api_response(sportsbook="onyx", results=raw_api_data)
            if not api_data:
                return

            leagues = self._extract_league_names(api_data)
            game_ids = await self._extract_game_ids(league_names=leagues, session=session, auth_token=auth_token)
            if not game_ids:
                return

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_url").format(game_id=game_id),
                    method=self.book_data.method,
                    headers={
                        "Authorization": f"Bearer {auth_token}"
                    }
                )
                for game_id in game_ids
            ]

            raw_results = await asyncio.gather(*tasks)

            results = self.check_api_response(sportsbook="onyx", results=raw_results)
            if not results:
                return

            all_mapped_ids = {}

            for api_data, game_id in zip(results, game_ids):
                if api_data:
                    mapped_ids = self._extract_mapped_ids(api_data, game_id)
                    all_mapped_ids.update(mapped_ids)

            if all_mapped_ids:
                with open("onyx_mapped_ids.json", "w") as f:
                    import json
                    json.dump(all_mapped_ids, f, indent=4)

                await redis.store_data("onyx_ids", all_mapped_ids, key_expiration=self.key_expiration)
                await redis.close()


if __name__ == "__main__":
    onyx_instance = Onyx_Mapper()
    asyncio.run(onyx_instance.run_book())