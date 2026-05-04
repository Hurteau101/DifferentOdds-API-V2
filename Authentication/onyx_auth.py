import os
from dotenv import load_dotenv
from curl_cffi import AsyncSession as CurlAsyncSession
from APScheduler.base_scheduler import BaseScheduler
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
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

        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'

        proxies = os.getenv("ONYX_PROXIES").split(",") if os.getenv("ONYX_PROXIES") else ""

        for proxy in proxies:
            browser = None
            try:
                split_proxy = proxy.split(":")
                server = ':'.join(split_proxy[0:2])
                username = split_proxy[2]
                password = split_proxy[3]

                async with async_playwright() as play:
                    browser = await play.firefox.launch(
                        headless=False,
                        proxy={
                            "server": server,
                            "username": username,
                            "password": password
                        },
                    )

                    page = await browser.new_page()
                    await Stealth().apply_stealth_async(page)

                    await page.goto("https://app.onyxodds.com/login")
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(3000)

                    logged_in = False
                    for attempt in range(3):
                        print(f"Login attempt {attempt + 1}...")

                        await page.fill('input[name="email"]', login_username)
                        await page.fill('input[name="password"]', login_password)
                        await page.wait_for_timeout(2000)

                        await page.evaluate("""
                            new Promise((resolve) => {
                                grecaptcha.ready(() => {
                                    grecaptcha.execute('6LdhQEEsAAAAABff6XVoV1RPLOitPR7T0vEKvzE6', {action: 'login'})
                                        .then(resolve);
                                });
                            })
                        """)

                        await page.click('button[type="submit"]')

                        try:
                            await page.wait_for_url("https://app.onyxodds.com/", timeout=15000)
                            print("Login successful - redirected to dashboard")
                            logged_in = True
                            break
                        except:
                            error_text = await page.inner_text('//html/body/main/div/div/div/div[2]/form/div[3]')
                            print(f"Attempt {attempt + 1} failed: {error_text}")
                            await page.wait_for_timeout(3000)
                            await page.goto("https://app.onyxodds.com/login", timeout=60000)
                            await page.wait_for_load_state('networkidle')
                            await page.wait_for_timeout(3000)

                    if not logged_in:
                        continue

                    session_data = await page.evaluate("fetch('/api/auth/session').then(r => r.json())")

                    if not session_data:
                        continue

                    auth_token = session_data.get("user", {}).get("accessToken")

                    if auth_token:
                        await redis_instance.store_data(
                            key_name="onyx_auth",
                            data_to_store=auth_token,
                            key_expiration=27000
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