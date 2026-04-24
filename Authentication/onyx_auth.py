import os
from dotenv import load_dotenv
from curl_cffi import AsyncSession as CurlAsyncSession
from APScheduler.base_scheduler import BaseScheduler
from playwright.async_api import async_playwright
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class OnyxAuth(BaseScheduler):
    load_dotenv()
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        login_username = os.getenv("ONYX_EMAIL")
        login_password = os.getenv("ONYX_PASSWORD")

        if not login_password or not login_username:
            raise ValueError("ONYX_EMAIL and ONYX_PASSWORD must be set in the environment variables.")

        # Used for Linux. Need to run this non-headless.
        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'

        proxies = os.getenv("ONYX_PROXIES").split(",") if os.getenv("ONYX_PROXIES") else ""

        for proxy in proxies:
            try:
                split_proxy = proxy.split(":")
                server = ':'.join(split_proxy[0:2])
                username = split_proxy[2]
                password = split_proxy[3]

                async with async_playwright() as play:
                    browser = await play.chromium.launch(
                        args=["--no-sandbox", "--disable-setuid-sandbox"],
                        headless=False,
                        proxy={
                            "server": server,
                            "username": username,
                            "password": password
                        },
                    )

                    page = await browser.new_page()
                    await page.goto("https://app.onyxodds.com/login")
                    await page.wait_for_load_state('networkidle')
                    await page.fill('input[name="email"]', login_username)
                    await page.fill('input[name="password"]', login_password)
                    await page.click('button[type="submit"]')
                    await page.wait_for_timeout(15000)

                    session_data = await page.evaluate("fetch('/api/auth/session').then(r => r.json())")

                    if not session_data:
                        continue

                    auth_token = session_data.get("user", {}).get("accessToken")

                    if auth_token:
                        await redis_instance.store_data(
                            key_name="onyx_auth",
                            data_to_store=auth_token,
                            key_expiration=27000  # 7.5 Hours
                        )

                        return True

            except Exception as e:
                print(f"OnyxAuth error with proxy {proxy}: {e}")
                continue

            finally:
                if browser is not None:
                    await browser.close()

        print("All proxies failed for OnyxAuth")
        return False


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            buck = OnyxAuth()
            await buck.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())