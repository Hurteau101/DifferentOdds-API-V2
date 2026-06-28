import asyncio
import os
import time

import aiohttp
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

class CaesarAuth(BaseScheduler):
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    def parse_proxy(self, proxy_str: str) -> dict:
        """Converts 'host:port:username:password' into Playwright's proxy dict."""
        host, port, username, password = proxy_str.split(":")
        return {
            "server": f"http://{host}:{port}",
            "username": username,
            "password": password,
        }

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager, proxy_index=None) -> bool:
        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'

        proxy = os.getenv("DECODO_PROXY")
        if not proxy:
            return False

        proxy_dict = self.parse_proxy(proxy) if proxy else None

        async with async_playwright() as p:
            for attempt in range(0, 5):
                browser = await p.chromium.launch(headless=False)

                try:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        proxy=proxy_dict
                    )

                    page = await context.new_page()

                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)

                    await page.goto("https://sportsbook.caesars.com/us/az/bet/", wait_until="networkidle")
                    await page.wait_for_timeout(5000) # Wait for any JS challenges to finish.

                    for _ in range(30):
                        cookies = await context.cookies()
                        waf_token = next((c["value"] for c in cookies if c["name"] == "aws-waf-token"), None)

                        if waf_token:
                            await redis_instance.store_data(
                                key_name="caesars_waf_token",
                                data_to_store=waf_token,
                                key_expiration=720
                            )

                            return True

                        await page.wait_for_timeout(500)

                except Exception as e:
                    pass

                finally:
                    await browser.close()

            return False

if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    redis_instance = RedisAsyncManager(database=5)
    caesar = CaesarAuth()
    async def main():
        async with aiohttp.ClientSession() as session:
            await caesar.run_scheduler(session, redis_instance)

    asyncio.run(main())

