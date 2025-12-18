import aiohttp
import asyncio
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Onyx_SGP(SGPBookBase):
    def __init__(self, links, **kwargs):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="onyx_sgp.log", sportsbook_name="onyxodds", links=links, **kwargs)

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

            if not mapped_ids:
                return None

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
                    if data is not None
                       and (bet_id := data.get("bet_id")) is not None
                       and bet_id in mapped_ids
                }
            }


            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers={
                    "Authorization": f"Bearer {auth_token}"
                },
                payload=payload
            )

            api_data = self.check_api_response(sportsbook="onyx", results=raw_api_data)
            if not api_data:
                return

            api_data.pop("success")

            if not api_data.get("price"):
                return None

            return {
                "american": float(api_data.get("price"))
            }

    async def _get_auth(self):
        redis = RedisManager(db=5)
        auth_token = await redis.get_auth_token("onyx_auth_token")
        await redis.close()
        return auth_token

if __name__ == "__main__":
    import asyncio

    links = [
        "https://app.onyxodds.com/game/78014-13184-25-44?selection=b568b221-6406-436c-90d4-0f633732b81b", # Rams -9.5
        "https://app.onyxodds.com/game/78014-13184-25-44?selection=ca9ecfba-165c-4d38-89c0-445d46d5079b",# Stafford over 2.5 pass TD
    ]

    onyx_sgp = Onyx_SGP(links=links)
    data = asyncio.run(onyx_sgp.run_book())
    print(data)