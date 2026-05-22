import asyncio
import os
import time

import aiohttp
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

class CaesarAuth(BaseScheduler):
    load_dotenv()
    MAX_RETRY = 2
    RETRY_DELAY = 0.5
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager, proxy_index=None) -> bool:

        proxy = os.getenv("RESIDENTIAL_PROXIES")
        if not proxy:
            create_sentry_message(
                tag_key="caesars",
                tag_value="proxy_failure",
                message="No proxy found",
                level="error"
            )
            return False

        # proxies = [proxy]
        proxies = proxy.split(",")

        async with async_playwright() as play:  # ← start once
            for index, proxy in enumerate(proxies):
                if proxy_index is not None and index <= proxy_index:
                    print("Skipping index:", index)
                    continue

                ip, port, username, password = proxy.split(":")

                browser = None

                try:
                    browser = await play.chromium.launch(
                        headless=True,
                        proxy={
                            "server": f"http://{ip}:{port}",
                            "username": username,
                            "password": password,
                        },

                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--start-maximized"
                        ]
                    )

                    context = await browser.new_context()

                    await context.route(
                        "**/*",
                        lambda route: (
                            route.abort()
                            if route.request.resource_type in ["image", "media", "font"]
                            else route.continue_()
                        )
                    )

                    page = await context.new_page()

                    await page.goto(
                        "https://sportsbook.caesars.com/us/az/bet/",
                        wait_until="networkidle",
                        timeout=60_000
                    )

                    await page.locator(
                        "//div[normalize-space()='Betslip']"
                    ).wait_for(state="visible", timeout=60_000)

                    cookies = await context.cookies()

                    waf_token = next((c["value"] for c in cookies if c["name"] == "aws-waf-token"), None)
                    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

                    if waf_token and cookie_str:
                        await redis_instance.store_data(
                            key_name="caesars_waf_token",
                            data_to_store={
                                "waf_token": waf_token,
                                "cookie_str": cookie_str,
                                "proxy_index": index,
                                "proxy_str": proxy
                            },
                            key_expiration=720
                        )
                        return True

                except Exception as e:
                    create_sentry_message(
                        tag_key="caesars",
                        tag_value="Exception",
                        message=str(e),
                        level="error"
                    )

                    print(e)

                    continue

                finally:
                    if browser:
                        await browser.close()



        create_sentry_message(
            tag_key="caesars",
            tag_value="auth_failure",
            message="WAF token not found after authentication attempts.",
            level="error"
        )

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

