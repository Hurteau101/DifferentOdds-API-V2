from dotenv import load_dotenv
from playwright.async_api import async_playwright
from Redis.redis_manager import RedisManager
import asyncio
import os

from Settings.logger import FileLogger

load_dotenv()
EMAIL = os.getenv("ONYX_EMAIL")
PASSWORD = os.getenv("ONYX_PASSWORD")

async def generate_onyx_auth_token():
    """Automates the login process to Onyx Odds and retrieves the session token."""
    redis = RedisManager(db=5)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto("https://app.onyxodds.com/login")

            await page.fill('input[name="email"]', EMAIL)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[type="submit"]')

            await page.wait_for_url("https://app.onyxodds.com/")

            response = await page.request.get("https://app.onyxodds.com/api/auth/session")

            # Auth Token
            data = await response.json()
            auth_token = data.get("user", {}).get("accessToken")
            if auth_token:
                await redis.store_auth_token(key_name="onyx_auth_token", value=auth_token, key_expiration=46800)
            else:
                base_directory = os.path.dirname(os.path.abspath(__file__))
                log_path = os.path.join(base_directory, "Logs")
                os.makedirs(log_path, exist_ok=True)
                log_file = os.path.join(log_path, "onyx_auth_error.log")
                logger = FileLogger()
                logger.set_log_file(log_file)
                logger.log(
                    sportsbook="Onyx",
                    message=f"Could not retrieve Onyx session token.",
                    level="ERROR"
                )
        finally:
            await page.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_onyx_auth_token())
