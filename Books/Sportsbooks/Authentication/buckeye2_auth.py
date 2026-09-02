import os
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes


class Buckeye2Auth(AuthBase):
    URL = "https://www.247bettor.com/cloud/api/System/authenticateCustomer"

    def __init__(self):
        super().__init__(book_name="buckeye2", category="sportsbooks")

    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            username = os.getenv("BUCKEYE_2_USERNAME")
            password = os.getenv("BUCKEYE_2_PASSWORD")

            if not username or not password:
                raise ValueError("Missing required environment variables: BUCKEYE_2_USERNAME, BUCKEYE_2_PASSWORD")

            response = await self.api_caller(
                url=Buckeye2Auth.URL,
                use_proxy=True,
                method="POST",
                json={
                    "customerID": username,
                    "state": "true",
                    "password": password,
                    "multiaccount": "1",
                    "response_type": "code",
                    "client_id": username,
                    "domain": "247bettor.com",
                    "redirect_uri": "247bettor.com",
                    "operation": "authenticateCustomer",
                    "RRO": "1",
                },
                headers={
                    "Authorization": "Bearer undefined",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.247bettor.com",
                    "Referer": "https://www.247bettor.com/",
                    "TE": "trailers",
                }
            )

            if not (isinstance(response, dict) and "code" in response):
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not extract auth token"
                )

                return False

            auth_token = response.get("code")

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=auth_token,
                expiration_time=1200  # 20 minutes
            )

            return True

if __name__ == "__main__":
    import asyncio
    buckeye_2 = Buckeye2Auth()
    asyncio.run(buckeye_2.run_auth())
