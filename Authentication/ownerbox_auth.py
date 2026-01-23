import os
import random
import aiohttp
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class OwnerboxAuth(BaseScheduler):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    def _randomize_login(self):
        """Used to randomize the login email from a list of emails."""
        emails = os.getenv("OWNERBOX_EMAILS")
        if not emails:
            return ""

        password = os.getenv("OWNERBOX_PASSWORD")

        email_list = emails.split(",")
        random_email = random.choice(email_list)

        return random_email, password

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        load_dotenv()

        email, password = self._randomize_login()

        if not email or not password:
            create_sentry_message(
                tag_key="ownerbox",
                tag_value="login_failure",
                message="Ownerbox login failed due to missing credentials.",
                level="error"
            )
            return

        async with async_playwright() as play:
            try:
                browser = await play.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = await browser.new_context()
                page = await context.new_page()

                # Go to login page
                await page.goto("https://app.ownersbox.com/wfs/login", timeout=60000)

                # Fill in login form
                await page.fill("//input[@placeholder='Enter your Email']", email)
                await page.fill("//input[@placeholder='Enter your password']", password)

                # Click login
                await page.click("//button[@class='ob-btn-primary']")

                # Wait until the dashboard loads
                await page.wait_for_selector("//a[@title='Home']")

                # Get cookies
                cookies = await context.cookies()
                obauth_cookie = next((c for c in cookies if c["name"] == "obauth"), None)

                if not obauth_cookie or not obauth_cookie.get("value"):
                    create_sentry_message(
                        tag_key="ownerbox",
                        tag_value="auth_failure",
                        message="Auth token not found in cookies after login.",
                        level="error"
                    )
                    return

                auth_token = str(obauth_cookie["value"])
                await redis_instance.store_data(
                    key_name="ownerbox_auth_token",
                    data_to_store=auth_token,
                    key_expiration=720  # 12 Minutes
                )

            except Exception:
                pass
            finally:
                await browser.close()
                await context.close()
