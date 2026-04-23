import os
from urllib.parse import urlencode

import aiohttp
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class FliffAuth(BaseScheduler):
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
        basic_auth = os.getenv("FLIFF_BASIC_AUTH_TOKEN")
        refresh_token = os.getenv("FLIFF_REFRESH_TOKEN")

        if not basic_auth or not refresh_token:
            raise ValueError("FLIFF_BASIC_AUTH_TOKEN and FLIFF_REFRESH_TOKEN must be set in environment variables.")

        response = await self.api_caller(
            book_name="fliff",
            session=session,
            url="https://app.getfliff.com/api/v1/oauth2/token/",
            method="POST",
            headers={
                'accept': 'application/json, text/plain, */*',
                'authorization': f'Basic {basic_auth}',
                'content-type': 'application/x-www-form-urlencoded',
            },
            payload=urlencode({
                'grant_type': 'refresh_token',
                'refresh_token': os.getenv("FLIFF_REFRESH_TOKEN"),
                'device_x_id': 'android.48e0c8468226f089'
            })
        ) or {}

        if response.get("access_token"):
            await redis_instance.store_data(
                key_name="fliff_auth_token",
                data_to_store=response["access_token"],
                key_expiration=response.get("expires_in", 300)  # 5 Minutes
            )

            return True

        return False





if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    redis_instance = RedisAsyncManager(database=5)
    fliff = FliffAuth()

    async def main():
        async with aiohttp.ClientSession() as session:
            await fliff.run_scheduler(session, redis_instance)

    asyncio.run(main())