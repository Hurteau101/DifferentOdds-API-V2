import os
from dotenv import load_dotenv
from Authentication.base_auth import BaseAuth
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class ChalkboardAuth(BaseAuth):
    def __init__(self):
        super().__init__(book_name="chalkboard", category="dfs")

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        load_dotenv()
        token_url = os.getenv("CHALKBOARD_TOKEN_URL")
        api_key = os.getenv("CHALKBOARD_API_KEY")
        headers = {
            "x-android-package": "com.taild",
            "x-android-cert": os.getenv("CHALKBOARD_ANDROID_CERT"),
            "accept-language": "en-US",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-A065F Build/UP1A.231005.007)",
            "Content-Type": "application/json",
        }

        payload = {
            "grantType": os.getenv("CHALKBOARD_GRANT_TYPE"),
            "refreshToken": os.getenv("CHALKBOARD_REFRESH_TOKEN")
        }

        response = await self.api_caller(
            session=session,
            url=f"{token_url}?key={api_key}",
            method="POST",
            headers=headers,
            payload=payload
        )

        auth = (response or {}).get("access_token", "")
        refresh = (response or {}).get("refresh_token", "")

        if not auth:
            return False

        previous_refresh = await redis_instance.get_data(
            key_name="chalkboard_refresh_token_backup"
        )

        # Store refresh token backup if available and not already stored
        if refresh and not previous_refresh:
            await redis_instance.store_data(
                key_name="chalkboard_refresh_token_backup",
                data_to_store=refresh,
                key_expiration=86400  # 1 Day
            )

        await redis_instance.store_data(
            key_name=self.auth_id_name,
            data_to_store=auth,
            key_expiration=5270400  # 61 Days
        )

        return True

if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    redis_instance = RedisAsyncManager(database=5)
    caesar = ChalkboardAuth()
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            await caesar.run_scheduler(session, redis_instance)

    asyncio.run(main())


