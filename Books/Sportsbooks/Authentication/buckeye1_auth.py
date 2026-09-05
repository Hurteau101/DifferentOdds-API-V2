import os
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes


class Buckeye1Auth(AuthBase):
    def __init__(self):
        super().__init__(book_name="buckeye1", category="sportsbooks")

    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            username = os.getenv("BUCKEYE_1_USERNAME")
            password = os.getenv("BUCKEYE_1_PASSWORD")

            if not username or not password:
                raise ValueError("BUCKEYE_1_USERNAME and BUCKEYE_1_PASSWORD must be set in the environment variables.")

            await session.post(
                "https://playnow365.com/Qubic/SecurityPage.php",
                headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://playnow365.com',
                    'Referer': 'https://playnow365.com/',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                },
                data=f'customerID={username}&password={password}&login.x=49&login.y=4',
                impersonate="firefox"
            )

            cookies = {
                cookie.name: cookie.value
                for cookie in session.cookies.jar
                if cookie.domain in ('.playnow365.com', 'playnow365.com')
            }

            if cookies:
                await self.store_data(
                    key_name=self.auth_id_name,
                    data_to_store=cookies,
                    expiration_time=self.pre_calculated_redis_expiration
                )

                return True

            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.AUTH,
                error_message="Could not extract cookies"
            )

            return False


if __name__ == "__main__":
    import asyncio
    buckeye_1 = Buckeye1Auth()
    asyncio.run(buckeye_1.run_auth())