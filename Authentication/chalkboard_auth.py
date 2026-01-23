import os
import aiohttp
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class ChalkboardAuth(BaseScheduler):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
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
            book_name="chalkboard",
            session=session,
            url=f"{token_url}?key={api_key}",
            method="POST",
            headers=headers,
            payload=payload
        )

        auth = (response or {}).get("access_token", "")
        refresh = (response or {}).get("refresh_token", "")

        if not auth:
            create_sentry_message(
                tag_key="chalkboard",
                tag_value="auth_failure",
                message="Auth token not found after authentication attempts.",
                level="error"
            )

            return

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
            key_name="chalkboard_access_token",
            data_to_store=auth,
            key_expiration=5270400  # 61 Days
        )
