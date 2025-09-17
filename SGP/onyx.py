from email.policy import default

import aiohttp

from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Onyx_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="onyx_sgp.log", sportsbook_name="onyx", links=links)
        self.redis = RedisManager(db=5)

    async def _get_cached_ids(self):
        redis = RedisManager(db=self.redis_db)
        mapped_ids = await redis.fetch_data("onyx_ids")
        await redis.close()
        return mapped_ids

    @SGPBookBase.require_link_data
    async def run_book(self):
        auth_token = await self._get_auth()
        async with aiohttp.ClientSession() as session:
            mapped_ids = await self._get_cached_ids()
            payload = {
                "betSelections": {
                    mapped_ids[data["bet_id"]]["semantic_id"]: {
                        "marketDetails": {
                            "name": mapped_ids[data["bet_id"]]["name"],
                            "marketName": mapped_ids[data["bet_id"]]["market_name"],
                            "game": {
                                "fixtureId": mapped_ids[data["bet_id"]]["fixture_id"]
                            }
                        }
                    }
                    for data in self.link_data
                    if data.get("bet_id") in mapped_ids
                }
            }

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers={
                    "Authorization": f"Bearer {auth_token}"
                },
                payload=payload
            )

            if not api_data or not api_data.get("price"):
                return None

            return {
                "american_odds": float(api_data.get("price"))
            }

    async def _get_auth(self):
        auth_token = await self.redis.fetch_data("onyx_auth_token")
        await self.redis.close()
        return auth_token

    def _extract_game_ids(self, api_data):
        return set(
            game_id
            for game_id in api_data.get("data").keys()
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


    async def store_onyx_data(self):
        auth_token = await self._get_auth()

        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("store_url"),
                method="GET",
                headers={
                    "Authorization": f"Bearer {auth_token}"
                }
            )

            if not api_data:
                self._api_call_log("onyx_sgp")
                return None

            game_ids = self._extract_game_ids(api_data)

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_url").format(game_id=game_id),
                    method="GET",
                    headers={
                        "Authorization": f"Bearer {auth_token}"
                    }
                )
                for game_id in game_ids
            ]

            results = await asyncio.gather(*tasks)
            all_mapped_ids = {}
            for api_data, game_id in zip(results, game_ids):
                if api_data:
                    mapped_ids = self._extract_mapped_ids(api_data, game_id)
                    all_mapped_ids.update(mapped_ids)

            if all_mapped_ids:
                redis_store = RedisManager(db=self.redis_db)
                await redis_store.store_data("onyx_ids", all_mapped_ids, key_expiration=600)
                await redis_store.close()


if __name__ == "__main__":
    import asyncio

    links = [
        "https://app.onyxodds.com/game/26757-33128-25-37?selection=c31ad330-c184-4140-8838-0149c27d87de",
        "https://app.onyxodds.com/game/26757-33128-25-37?selection=9c3372ab-9d00-4177-8d78-d58fd2657847"
    ]
    onyx_sgp = Onyx_SGP(links=links)

    run_type = ""
    if run_type == "store":
        asyncio.run(onyx_sgp.store_onyx_data())
    else:
        data = asyncio.run(onyx_sgp.run_book())
        print(data)