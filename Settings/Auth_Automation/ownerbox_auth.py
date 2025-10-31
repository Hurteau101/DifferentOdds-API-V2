import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import asyncio
from Redis.redis_manager import RedisManager

load_dotenv()
EMAIL = os.getenv("OWNERBOX_EMAIL")
PASSWORD = os.getenv("OWNERBOX_PASSWORD")

async def generate_ownerbox_auth_token():
    redis = RedisManager(db=5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Go to login page
        await page.goto("https://app.ownersbox.com/wfs/login", timeout=60000)

        # Fill in login form
        await page.fill("//input[@placeholder='Enter your Email']", EMAIL)
        await page.fill("//input[@placeholder='Enter your password']", PASSWORD)

        # Click login
        await page.click("//button[@class='ob-btn-primary']")

        # Wait until the dashboard loads
        await page.wait_for_selector("//a[@title='Home']")

        # Get cookies
        cookies = await context.cookies()
        obauth_cookie = next((c for c in cookies if c["name"] == "obauth"), None)

        if obauth_cookie:
            auth_token = obauth_cookie["value"]

            if auth_token:
                await redis.store_data(
                    key_name="ownerbox_auth_token",
                    data_to_store=auth_token,
                    key_expiration=46800
                )
                await redis.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_ownerbox_auth_token())