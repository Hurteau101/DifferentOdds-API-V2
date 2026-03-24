import asyncio
import os
import aiohttp
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class FourcxAuth(BaseScheduler):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        payload = {
            "username": os.getenv("4CX_USERNAME"),
            "password": os.getenv("4CX_PASSWORD")
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'x-user-socket-status': '',
            'x-price-socket-status': '',
            'Origin': 'https://4cx.io',
            'Connection': 'keep-alive',
            'Referer': 'https://4cx.io/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }

        response = await self.api_caller(
            book_name="4cx",
            session=session,
            url="https://api.4cx.io/user/login",
            method="POST",
            headers=headers,
            payload=payload
        )

        auth = (response or {}).get("data", {}).get("user", {}).get("auth")

        if not auth:
            create_sentry_message(
                tag_key="fourcx",
                tag_value="auth_failure",
                message="Auth token not found after authentication attempts.",
                level="error"
            )

            return

        await redis_instance.store_data(
            key_name="4cx_auth_token",
            data_to_store=auth,
            key_expiration=5270400  # 61 Days
        )

if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            fourcx = FourcxAuth()
            await fourcx.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())

