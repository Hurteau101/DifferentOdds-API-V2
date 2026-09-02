import os
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from curl_cffi import AsyncSession as CurlAsyncSession

class FourcxAuth(AuthBase):
    def __init__(self):
        super().__init__(book_name="4cx", category="prediction_liquidity")

    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
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
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not extract auth token"
                )

                return False

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=auth,
                expiration_time=5270400  # 61 Days
            )

            return True

if __name__ == "__main__":
    import asyncio
    four_cx = FourcxAuth()
    asyncio.run(four_cx.run_auth())

