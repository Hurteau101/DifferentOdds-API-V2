import os
import aiohttp
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class OnyxAuth(BaseScheduler):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        load_dotenv()
        async with async_playwright() as play:
            browser = await play.firefox.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto("https://app.onyxodds.com/login")
                await page.fill('input[name="email"]', os.getenv("ONYX_EMAIL"))
                await page.fill('input[name="password"]', os.getenv("ONYX_PASSWORD"))
                await page.click('button[type="submit"]')

                await page.wait_for_url("https://app.onyxodds.com/")

                response = await page.request.get("https://app.onyxodds.com/api/auth/session")

                # Auth Token
                data = await response.json()
                auth_token = data.get("user", {}).get("accessToken")
                if not auth_token:
                    create_sentry_message(
                        tag_key="onyx",
                        tag_value="auth_failure",
                        message="Auth token not found after authentication attempts.",
                        level="error"
                    )
                    return

                await redis_instance.store_data(
                    key_name="onyx_auth_token",
                    data_to_store=auth_token,
                    key_expiration=21600 # 6 hours
                )


            except Exception as e:
                create_sentry_message(
                    tag_key="onyx",
                    tag_value="auth_failure",
                    message=f"Auth retrieval failed with exception: {e}",
                    level="error"
                )
                return
            finally:
                await page.close()
                await browser.close()


if __name__ == "__main__":
    import asyncio

    async def main():
        redis_instance = RedisAsyncManager(database=11)
        auth_instance = OnyxAuth()

        async with aiohttp.ClientSession() as session:
            await auth_instance.run_scheduler(
                session=session,
                redis_instance=redis_instance
            )

        await redis_instance.close_for_shutdown()

    asyncio.run(main())