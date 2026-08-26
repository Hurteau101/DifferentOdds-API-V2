import os
from dotenv import load_dotenv
from curl_cffi import AsyncSession as CurlAsyncSession

from Authentication.base_auth import BaseAuth


class AceAuth(BaseAuth):
    URL = "https://backend.betvegas23.com/Login.aspx"
    load_dotenv()

    def __init__(self):
        super().__init__(book_name="ace", category="sportsbooks")

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance) -> bool:
        await session.post(
            url=AceAuth.URL,
            data={
                "account": os.getenv("ACE_USERNAME"),
                "password": os.getenv("ACE_PASSWORD"),
            },
            headers={
                "Referer": "https://betvegas23.com/",
                "Origin": "https://betvegas23.com",
            })

        await redis_instance.store_data(
            key_name=self.auth_id_name,
            data_to_store=session.cookies.get_dict(),
            key_expiration=1200  # 20 Minutes
        )

        return True


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="chrome") as session:
            ace = AceAuth()
            await ace.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())