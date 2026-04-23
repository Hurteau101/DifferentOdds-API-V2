import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
import aiohttp
from yarl import URL

class AceAuth(BaseScheduler):
    URL = "https://backend.betvegas23.com/Login.aspx"
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance) -> bool:
        await session.post(
            url=AceAuth.URL,
            data={
                "account": os.getenv("ACE_USERNAME"),
                "password": os.getenv("ACE_PASSWORD"),
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://betvegas23.com/",
                "Origin": "https://betvegas23.com",
            })

        cookies = session.cookie_jar.filter_cookies(URL(AceAuth.URL))
        cookie_dict = {name: morsel.value for name, morsel in cookies.items()}

        if not cookie_dict:
            return False

        await redis_instance.store_data(
            key_name="ace_cookies",
            data_to_store=cookie_dict,
            key_expiration=1200 # 20 Minutes
        )

        return True


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            ace = AceAuth()
            await ace.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())