import asyncio
import os
from Authentication.base_auth import BaseAuth
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class FourcxAuth(BaseAuth):
    def __init__(self):
        super().__init__(book_name="kibl", category="prediction_liquidity")

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        payload = {
            "username": os.getenv("4CX_USERNAME"),
            "password": os.getenv("4CX_PASSWORD")
        }

        headers = {
            'Content-Type': 'application/json',
            'x-user-socket-status': '',
            'x-price-socket-status': '',
            'Origin': 'https://4cx.io',
            'Connection': 'keep-alive',
            'Referer': 'https://4cx.io/',
        }

        response = await self.api_caller(
            session=session,
            url="https://api.4cx.io/user/login",
            method="POST",
            headers=headers,
            json=payload
        )

        auth = (response or {}).get("data", {}).get("user", {}).get("auth")

        if not auth:
            return False

        await redis_instance.store_data(
            key_name=self.auth_id_name,
            data_to_store=auth,
            key_expiration=5270400  # 61 Days
        )

        return True

if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="chrome") as session:
            fourcx = FourcxAuth()
            await fourcx.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())

