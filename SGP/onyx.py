import aiohttp

from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Onyx_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="onyx_sgp.log", sportsbook_name="onyx", links=links)
        self.redis = RedisManager(db=5)

    @SGPBookBase.require_link_data
    async def run_book(self):
        pass

    async def _get_auth(self):
        auth_token = await self.redis.fetch_data("onyx_auth_token")
        await self.redis.close()
        return auth_token

    def _extract_game_ids(self, api_data):
        pass


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



if __name__ == "__main__":
    import asyncio

    links = [
        "https://www.onyxbet.com/en/sportsbook/event/123456789/some-event/some-bet?some_param=value",
        "https://www.onyxbet.com/en/sportsbook/event/987654321/another-event/another-bet?some_param=value",
    ]
    onyx_sgp = Onyx_SGP(links=links)

    run_type = "store"
    if run_type == "store":
        asyncio.run(onyx_sgp.store_onyx_data())
    else:
        asyncio.run(onyx_sgp.run_book())
