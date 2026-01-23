import os
import aiohttp
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class KiblAuth(BaseScheduler):
    URL = "https://cognito-idp.us-west-2.amazonaws.com/"
    HEADERS = {
        'accept': 'application/json',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        'Content-Type': 'application/x-amz-json-1.1'
    }

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)


    def _extract_auth_refresh(self, response: dict):
        """Extract auth token, refresh token, and expiry from the response."""
        return (
            response.get("AuthenticationResult", {}).get("AccessToken"),
            response.get("AuthenticationResult", {}).get("RefreshToken"),
            response.get("AuthenticationResult", {}).get("ExpiresIn")
        )

    async def get_auth_from_refresh(self, session: aiohttp.ClientSession, refresh_token: str):
        """Get the auth token using the refresh token."""
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": os.getenv("KIBL_APP_CLIENT"),
            "AuthParameters": {
                "REFRESH_TOKEN": refresh_token
            }
        }

        response = await self.api_caller(
            book_name="kbil",
            session=session,
            url=KiblAuth.URL,
            method="POST",
            headers=KiblAuth.HEADERS,
            payload=payload
        )

        return self._extract_auth_refresh(response)

    async def get_auth_without_refresh(self, session: aiohttp.ClientSession) -> tuple:
        """Get the auth token without using the refresh token."""
        payload = {
            "AuthParameters": {
                "USERNAME": os.getenv("KIBL_USERNAME"),
                "PASSWORD": os.getenv("KIBL_PASSWORD")
            },
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": os.getenv("KIBL_APP_CLIENT")
        }

        response = await self.api_caller(
            book_name="kbil",
            session=session,
            url=KiblAuth.URL,
            method="POST",
            headers=KiblAuth.HEADERS,
            payload=payload
        )

        return self._extract_auth_refresh(response)


    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        load_dotenv()

        previous_refresh_token = await redis_instance.get_data(key_name="kibl_refresh_token")

        if not previous_refresh_token:
            auth, refresh, expiry = await self.get_auth_without_refresh(session=session)
            if not auth or not refresh or not expiry:
                create_sentry_message(
                    tag_key="kibl",
                    tag_value="auth_failure",
                    message="Auth token not found after authentication attempts.",
                    level="error"
                )
                return

            await redis_instance.store_data(
                key_name="kibl_refresh_token",
                data_to_store=refresh,
                key_expiration=2678400  # 31 Days
            )

            await redis_instance.store_data(
                key_name="kibl_auth_token",
                data_to_store=auth,
                key_expiration=expiry  # 61 Days
            )

            return


        auth, refresh, expiry = await self.get_auth_from_refresh(session=session, refresh_token=previous_refresh_token)

        if not auth or not expiry:
            create_sentry_message(
                tag_key="kibl",
                tag_value="auth_failure",
                message="Auth token not found after authentication attempts.",
                level="error"
            )
            return

        await redis_instance.store_data(
            key_name="kibl_auth_token",
            data_to_store=auth,
            key_expiration=82800  # 61 Days
        )


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            kibl_auth = KiblAuth()
            await kibl_auth.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())

