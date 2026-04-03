import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
import aiohttp
from yarl import URL

class BetVegasAuth(BaseScheduler):
    URL = "https://backend.betvegas23.com/Login.aspx"
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance):
        await session.post(
            url=BetVegasAuth.URL,
            data={
                "account": os.getenv("1BV_USERNAME"),
                "password": os.getenv("1BV_PASSWORD"),
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://betvegas23.com/",
                "Origin": "https://betvegas23.com",
            })

        cookies = session.cookie_jar.filter_cookies(URL(BetVegasAuth.URL))
        cookie_dict = {name: morsel.value for name, morsel in cookies.items()}
        if not cookie_dict:
            return

        await redis_instance.store_data(
            key_name="1bv_cookies",
            data_to_store=cookie_dict,
            key_expiration=1200 # 20 Minutes
        )


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            betvegas = BetVegasAuth()
            await betvegas.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())