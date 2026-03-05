import os
import random
from typing import cast, Any
import aiohttp
from dotenv import load_dotenv
from playwright.async_api import async_playwright, ProxySettings
from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType


class OnyxAuth(BaseScheduler):
    load_dotenv()
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        raw_proxy = os.getenv("ONYX_PROXY")
        if not raw_proxy:
            create_sentry_message(
                tag_key="onyx",
                tag_value="proxy_failure",
                message=f"No proxy found",
                level="error"
            )

        host, port, user, password = raw_proxy.split(":") if raw_proxy else None

        proxy = {
            "server": f"http://{host}:{port}",
            "username": user,
            "password": password,
        }

        print(proxy)

        async with async_playwright() as play:
            browser = await play.firefox.launch(
                headless=False,
                # channel="chrome",
                proxy=proxy,
                # args=[
                #     "--no-sandbox",
                #     "--disable-dev-shm-usage",
                #     "--disable-gpu",
                #     "--disable-features=IsolateOrigins,site-per-process",
                # ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                locale="en-US",


            )


            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            """)

            page = await context.new_page()

            await page.set_extra_http_headers({
                'sec-ch-ua': '"Chromium";v="125", "Not.A/Brand";v="24"'
            })

            try:
                await page.goto("https://app.onyxodds.com/login")
                await asyncio.sleep(1000)
                await page.wait_for_timeout(random.randint(500, 900))

                await page.fill('input[name="email"]', os.getenv("ONYX_EMAIL"))
                await page.wait_for_timeout(random.randint(300, 600))
                await page.fill('input[name="password"]', os.getenv("ONYX_PASSWORD"))
                await page.wait_for_timeout(random.randint(300, 600))

                sign_button = page.locator('button[type="submit"]')

                # Logic in here,as when you sign in, sometimes will say invalid credentials. If you
                # click sign in again, it typically works.
                for _ in range(3):
                    await sign_button.click()

                    try:
                        await page.wait_for_url("https://app.onyxodds.com/", timeout=5_000)
                        break  # Login Successful
                    except:
                        # Invalid Login - Retry
                        await asyncio.sleep(2)

                response = await page.request.get("https://app.onyxodds.com/api/auth/session")
                await page.screenshot(path="01_login_page.png", full_page=True)

                # Auth Token
                data = await response.json()
                auth_token = data.get("user", {}).get("accessToken")
                print(auth_token)
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
                print(e)
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


# import os
# import time
# import random
# import asyncio
# import aiohttp
# from dotenv import load_dotenv
# from camoufox import Camoufox
#
# from APScheduler.base_scheduler import BaseScheduler
# from Monitoring.monitoring import create_sentry_message
# from Redis.redis_manager import RedisAsyncManager
# from Utils.request_caller import SportbookRequestType
#
# load_dotenv()
#
#
# # =====================================================
# # SYNC CAMOUFOX LOGIN WORKER (RUNS IN THREAD)
# # =====================================================
# def camoufox_login(proxy, email, password):
#     with Camoufox(
#         headless=False,   # ❗ MUST be headful
#         proxy=proxy,
#         geoip=True,       # align fingerprint with proxy
#     ) as browser:
#
#         context = browser.new_context()
#         page = context.new_page()
#         time.sleep(10)
#         page.goto("https://google.com")
#         time.sleep(random.uniform(0.4, 0.7))
#         # -----------------------------
#         # Go to login page
#         # -----------------------------
#         # page.goto("https://app.onyxodds.com/login")
#         page.goto("https://app.onyxodds.com/login")
#         # time.sleep(2.5)  # ❗ REQUIRED — let JS fully load
#         time.sleep(30)
#         # -----------------------------
#         # Fill email (with blur)
#         # -----------------------------
#         page.focus('input[name="email"]')
#         page.fill('input[name="email"]', email)
#         time.sleep(random.uniform(0.4, 0.7))
#
#         # Moving focus causes blur
#         page.focus('input[name="password"]')
#         time.sleep(random.uniform(0.4, 0.7))
#
#         # -----------------------------
#         # Fill password (with blur)
#         # -----------------------------
#         page.fill('input[name="password"]', password)
#         # page.fill('input[name="password"]', "global")
#         time.sleep(random.uniform(0.5, 0.9))
#
#         # Blur password by clicking body
#         page.mouse.click(50, 50)
#         time.sleep(0.6)
#
#         sign_button = page.locator('button[type="submit"]')
#
#         # -----------------------------
#         # LOGIN ATTEMPTS (HUMAN-LIKE)
#         # -----------------------------
#         for attempt in range(20):
#             print(f"[ONYX] Login attempt {attempt + 1}")
#
#             # page.fill('input[name="password"]', password)
#
#             # Mouse movement matters
#             page.mouse.move(
#                 random.randint(200, 600),
#                 random.randint(200, 500)
#             )
#             time.sleep(0.4)
#
#             sign_button.click()
#             time.sleep(1.8)  # ❗ allow validation
#
#             try:
#                 page.wait_for_url(
#                     "https://app.onyxodds.com/",
#                     timeout=7_000
#                 )
#                 print("[ONYX] Login successful")
#                 break
#             except:
#                 print("[ONYX] Login failed, retrying...")
#                 page.screenshot(path="onyx_login_failed.png", full_page=True)
#                 page.bring_to_front()
#                 time.sleep(2.5)
#         else:
#             page.screenshot(path="onyx_login_failed.png", full_page=True)
#             raise RuntimeError("Onyx login failed after multiple attempts")
#
#         # -----------------------------
#         # POST-LOGIN SETTLE TIME
#         # -----------------------------
#         time.sleep(3.0)
#
#         # -----------------------------
#         # DEBUG PROOF
#         # -----------------------------
#         page.screenshot(path="onyx_logged_in.png", full_page=True)
#         print("[ONYX] Final URL:", page.url)
#
#         # -----------------------------
#         # FETCH AUTH SESSION
#         # -----------------------------
#         response = page.request.get(
#             "https://app.onyxodds.com/api/auth/session"
#         )
#
#         if response.status != 200:
#             print("[ONYX] Session status:", response.status)
#             print("[ONYX] Session text:", response.text())
#             return None
#
#         data = response.json()
#         return data.get("user", {}).get("accessToken")
#
#
# # =====================================================
# # ASYNC SCHEDULER
# # =====================================================
# class OnyxAuth(BaseScheduler):
#     def __init__(self):
#         super().__init__(request_type=SportbookRequestType.ASYNC)
#
#     async def run_scheduler(
#         self,
#         session: aiohttp.ClientSession,
#         redis_instance: RedisAsyncManager
#     ):
#         raw_proxy = os.getenv("ONYX_PROXY")
#         if not raw_proxy:
#             create_sentry_message(
#                 tag_key="onyx",
#                 tag_value="proxy_failure",
#                 message="No proxy found",
#                 level="error"
#             )
#             return
#
#         host, port, user, password = raw_proxy.split(":")
#         proxy = {
#             "server": f"http://{host}:{port}",
#             "username": user,
#             "password": password,
#         }
#
#         auth_token = await asyncio.to_thread(
#             camoufox_login,
#             proxy,
#             os.getenv("ONYX_EMAIL"),
#             os.getenv("ONYX_PASSWORD"),
#         )
#
#         print(auth_token)
#
#         if not auth_token:
#             create_sentry_message(
#                 tag_key="onyx",
#                 tag_value="auth_failure",
#                 message="Auth token not found after login",
#                 level="error"
#             )
#             return
#
#         await redis_instance.store_data(
#             key_name="onyx_auth_token",
#             data_to_store=auth_token,
#             key_expiration=21600  # 6 hours
#         )
#
#         print("[ONYX] Auth token stored successfully")
#
#
# # =====================================================
# # ENTRYPOINT
# # =====================================================
# if __name__ == "__main__":
#     async def main():
#         redis_instance = RedisAsyncManager(database=11)
#         auth_instance = OnyxAuth()
#
#         async with aiohttp.ClientSession() as session:
#             await auth_instance.run_scheduler(
#                 session=session,
#                 redis_instance=redis_instance
#             )
#
#         await redis_instance.close_for_shutdown()
#
#     asyncio.run(main())


