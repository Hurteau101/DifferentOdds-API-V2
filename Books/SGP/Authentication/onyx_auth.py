import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from Books.Bases.auth_base import AuthBase
import aiohttp, re
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Utils.request_caller import PredefinedProxy
import asyncio
from loguru import logger


class OnyxAuth(AuthBase):
    EMAIL_OTP_EMAIL = os.getenv("EMAIL_OTP_EMAIL")
    EMAIL_OTP_PASSWORD = os.getenv("EMAIL_OTP_PASSWORD")
    EMAIL_CLIENT_BASE_URL = "https://api.mail.tm"

    def __init__(self):
        super().__init__(book_name="onyx odds", category="sgp")

    async def _extract_otp(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{OnyxAuth.EMAIL_CLIENT_BASE_URL}/token", json={"address": OnyxAuth.EMAIL_OTP_EMAIL, "password": OnyxAuth.EMAIL_OTP_PASSWORD}) as response:
                token = (await response.json())["token"]

            headers = {"Authorization": f"Bearer {token}"}

            for _ in range(15):
                async with session.get(f"{OnyxAuth.EMAIL_CLIENT_BASE_URL}/messages", headers=headers) as r:
                    messages = (await r.json())["hydra:member"]

                unread = [message for message in messages if not message["seen"]]
                if unread:
                    msg_id = unread[0]["id"]
                    async with session.get(f"{OnyxAuth.EMAIL_CLIENT_BASE_URL}/messages/{msg_id}", headers=headers) as r:
                        msg = await r.json()

                    # Delete the message, so there is no conflict.
                    async with session.delete(f"{OnyxAuth.EMAIL_CLIENT_BASE_URL}/messages/{msg_id}", headers=headers):
                        pass

                    body = msg.get("text") or msg.get("html") or ""
                    match = re.search(r'\b\d{6}\b', body)
                    if match:
                        return match.group()

                await asyncio.sleep(2)

        return None

    async def _start_up(self, page):
        await page.goto("https://google.com")
        await page.wait_for_timeout(2000)

        await page.goto("https://app.onyxodds.com/login")
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(3000)

    async def run_auth(self) -> bool:
        login_username = os.getenv("ONYX_EMAIL")
        login_password = os.getenv("ONYX_PASSWORD")

        if not login_password or not login_username:
            raise ValueError("ONYX_EMAIL and ONYX_PASSWORD must be set in the environment variables.")

        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'

        proxies = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value

        for proxy in proxies:
            browser = None
            try:
                split_proxy = proxy.split("@")
                server = split_proxy[1]
                username, password = split_proxy[0].split(":")

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

                    # Warm up browser, to try to give it more browsing history to help improve captcha score.
                    await self._start_up(page)

                    logged_in = False
                    for attempt in range(3):
                        logger.info(f"Attempting login attempt {attempt + 1}...")

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
                            await page.wait_for_selector('input[name="emailCode"]', timeout=10000)
                            logger.info("2FA required, fetching OTP...")

                            otp = await self._extract_otp()
                            if not otp:
                                logger.error("Failed to get OTP")
                                await self._start_up(page)
                                continue

                            logger.info(f"OTP received: {otp}")
                            await page.fill('input[name="emailCode"]', otp)
                            await page.click('button[type="submit"]')

                            await page.wait_for_timeout(3000)

                            invalid_code_locator = page.locator(
                                "form p:has-text('Invalid verification code'), .text-destructive")
                            if await invalid_code_locator.count() > 0:
                                logger.error("OTP acquired, but webpage rejected it as invalid.")
                                await self._start_up(page)
                                continue


                        except:
                            pass
                        try:
                            await page.wait_for_url("https://app.onyxodds.com/", timeout=15000)
                            logger.info("Login successful - redirected to dashboard")
                            logged_in = True
                            break
                        except:
                            error_text = await page.inner_text('//html/body/main/div/div/div/div[2]/form/div[3]')
                            logger.error(f"Attempt {attempt + 1} failed: {error_text}")
                            await page.wait_for_timeout(3000)
                            await page.goto("https://app.onyxodds.com/login", timeout=60000)
                            await page.wait_for_load_state('networkidle')
                            await page.wait_for_timeout(3000)

                    if not logged_in:
                        await self._start_up(page)
                        continue

                    session_data = await page.evaluate("fetch('/api/auth/session').then(r => r.json())")

                    if not session_data:
                        await self._start_up(page)
                        continue

                    auth_token = session_data.get("user", {}).get("accessToken")

                    if auth_token:
                        await self.store_data(
                            key_name=self.auth_id_name,
                            data_to_store=auth_token,
                            expiration_time=27000
                        )

                        return True

            except Exception as e:
                logger.warning(f"OnyxAuth error with proxy {proxy}: {e}")
                continue

            finally:
                if browser is not None:
                    await browser.close()

        insert_log(
            book_name=self.book_data.title,
            error_type=ErrorTypes.AUTH,
            error_message="All proxies failed, could not extract auth"
        )

        return False


if __name__ == "__main__":
    onyx_auth = OnyxAuth()
    asyncio.run(onyx_auth.run_auth())

