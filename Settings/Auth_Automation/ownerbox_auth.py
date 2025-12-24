import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import asyncio
from Redis.redis_manager import RedisManager
import random


def _randomize_login():
    load_dotenv()
    emails = os.getenv("OWNERBOX_EMAILS")
    if not emails:
        return ""

    password = os.getenv("OWNERBOX_PASSWORD")

    email_list = emails.split(",")
    random_email = random.choice(email_list)

    return random_email, password

async def generate_ownerbox_auth_token():
    redis = RedisManager(db=5)
    email, password = _randomize_login()

    if not email or not password:
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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

        if obauth_cookie:
            auth_token = obauth_cookie["value"]

            if auth_token:
                await redis.store_auth_token(
                    key_name="ownerbox_auth_token",
                    value=auth_token,
                    key_expiration=300
                )
                await redis.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_ownerbox_auth_token())