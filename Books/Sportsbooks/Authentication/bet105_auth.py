import os
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from curl_cffi import AsyncSession as CurlAsyncSession

class Bet105Auth(AuthBase):
    URL = "https://cognito-idp.us-west-2.amazonaws.com/"
    HEADERS = {
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        'Content-Type': 'application/x-amz-json-1.1'
    }

    def __init__(self):
        super().__init__(book_name="bet105", category="sportsbooks")

    def _extract_auth_refresh(self, response: dict):
        """Extract auth token, refresh token, and expiry from the response."""
        return (
            response.get("AuthenticationResult", {}).get("AccessToken"),
            response.get("AuthenticationResult", {}).get("RefreshToken"),
            response.get("AuthenticationResult", {}).get("ExpiresIn")
        )

    async def get_auth_from_refresh(self, session: CurlAsyncSession, refresh_token: str):
        """Get the auth token using the refresh token."""
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": os.getenv("KIBL_APP_CLIENT"),
            "AuthParameters": {
                "REFRESH_TOKEN": refresh_token
            }
        }

        response = await self.api_caller(
            session=session,
            url=Bet105Auth.URL,
            method="POST",
            headers=Bet105Auth.HEADERS,
            json=payload
        )

        return self._extract_auth_refresh(response)

    async def get_auth_without_refresh(self, session: CurlAsyncSession) -> tuple:
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
            session=session,
            url=Bet105Auth.URL,
            method="POST",
            headers=Bet105Auth.HEADERS,
            json=payload
        )

        return self._extract_auth_refresh(response)


    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            previous_refresh_token = await self.redis_manager.get_data(key_name="bet105_refresh_token")

            if not previous_refresh_token:
                auth, refresh, expiry = await self.get_auth_without_refresh(session=session)

                if not auth or not refresh or not expiry:
                    insert_log(
                        book_name=self.book_data.title,
                        error_type=ErrorTypes.AUTH,
                        error_message="No auth, refresh, or expiry found (without refresh)"
                    )

                    return False

                await self.store_data(
                    key_name="bet105_refresh_token",
                    data_to_store=refresh,
                    expiration_time=2678400  # 31 Days
                )

                await self.store_data(
                    key_name=self.auth_id_name,
                    data_to_store=auth,
                    expiration_time=expiry  # 61 Days
                )

                return True


            auth, refresh, expiry = await self.get_auth_from_refresh(session=session, refresh_token=previous_refresh_token)

            if not auth or not expiry:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="No auth or expiry found (with refresh)"
                )

                return False

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=auth,
                expiration_time=82800  # 61 Days
            )

            return True


if __name__ == "__main__":
    import asyncio
    bet105 = Bet105Auth()
    asyncio.run(bet105.run_auth())


