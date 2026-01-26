import asyncio
import aiohttp
from playwright.async_api import async_playwright
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

class CaesarAuth(BaseScheduler):
    MAX_RETRY = 5
    RETRY_DELAY = 0.5
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)


    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        for attempt in range(CaesarAuth.MAX_RETRY):
            browser = None
            context = None

            try:
                async with async_playwright() as play:
                    browser = await play.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"]
                    )

                    context = await browser.new_context()
                    page = await context.new_page()

                    await page.goto(
                        "https://sportsbook.caesars.com/us/az/bet/",
                        wait_until="networkidle"
                    )

                    await page.locator(
                        "//div[normalize-space()='Betslip']"
                    ).wait_for(state="visible", timeout=120_000)

                    cookies = await context.cookies()

                    waf_token = next(
                        (cookie["value"] for cookie in cookies if cookie["name"] == "aws-waf-token"),
                        None
                    )


                    if waf_token:
                        print(waf_token)
                        await redis_instance.store_data(
                            key_name="caesars_waf_token",
                            data_to_store=waf_token,
                            key_expiration=720  # 12 Minutes
                        )

                        return

            except Exception:
                continue
            finally:
                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        pass

                if browser is not None:
                    try:
                        await browser.close()
                    except Exception:
                        pass


            await asyncio.sleep(CaesarAuth.RETRY_DELAY)

        # If we reach here, all attempts have failed
        create_sentry_message(
            tag_key="caesars",
            tag_value="auth_failure",
            message="WAF token not found after authentication attempts.",
            level="error"
        )
