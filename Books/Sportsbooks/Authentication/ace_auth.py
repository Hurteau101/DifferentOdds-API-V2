import os
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes


class AceAuth(AuthBase):
    URL = "https://backend.betvegas23.com/Login.aspx"

    def __init__(self):
        super().__init__(book_name="ace", category="sportsbooks")

    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            await session.post(
                url=AceAuth.URL,
                data={
                    "account": os.getenv("ACE_USERNAME"),
                    "password": os.getenv("ACE_PASSWORD"),
                },
                headers={
                    "Referer": "https://betvegas23.com/",
                    "Origin": "https://betvegas23.com",
                })

            cookies = session.cookies.get_dict()
            if not cookies:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not extract cookies"
                )

                return False

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=session.cookies.get_dict(),
                expiration_time=1200  # 20 Minutes
            )

            return True


if __name__ == "__main__":
    import asyncio
    ace = AceAuth()
    asyncio.run(ace.run_auth())