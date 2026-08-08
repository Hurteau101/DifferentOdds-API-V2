import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from curl_cffi import AsyncSession as CurlAsyncSession


class Buckeye1Auth(BaseScheduler):
    load_dotenv()

    def __init__(self):
        super().__init__()


    async def run_scheduler(self, session: CurlAsyncSession, redis_instance) -> bool:
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
            await redis_instance.store_data(
                key_name="buckeye1_cookies",
                data_to_store=cookies,
                key_expiration=1200  # 20 Minutes
            )

            return True

        return False


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            buck = Buckeye1Auth()
            await buck.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())