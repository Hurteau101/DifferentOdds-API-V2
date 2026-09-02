import os
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from curl_cffi import AsyncSession as CurlAsyncSession

class ChalkboardAuth(AuthBase):
    def __init__(self):
        super().__init__(book_name="chalkboard", category="dfs")

    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            token_url = os.getenv("CHALKBOARD_TOKEN_URL")
            api_key = os.getenv("CHALKBOARD_API_KEY")
            headers = {
                "x-android-package": "com.taild",
                "x-android-cert": os.getenv("CHALKBOARD_ANDROID_CERT"),
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
                json=payload
            )

            auth = (response or {}).get("access_token", "")
            refresh = (response or {}).get("refresh_token", "")

            if not auth:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not extract auth token"
                )
                return False

            previous_refresh = await self.redis_manager.get_data(
                key_name="chalkboard_refresh_token_backup"
            )

            # Store refresh token backup if available and not already stored
            if refresh and not previous_refresh:
                await self.store_data(
                    key_name="chalkboard_refresh_token_backup",
                    data_to_store=refresh,
                    expiration_time=86400  # 1 Day
                )

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=auth,
                expiration_time=5270400  # 61 Days
            )

            return True

if __name__ == "__main__":
    import asyncio
    chalkboard = ChalkboardAuth()
    asyncio.run(chalkboard.run_auth())


