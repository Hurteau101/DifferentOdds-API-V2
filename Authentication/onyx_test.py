import os
import time
import random
import asyncio
import aiohttp
from dotenv import load_dotenv
from camoufox import Camoufox

from APScheduler.base_scheduler import BaseScheduler
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType

load_dotenv()

STORAGE_PATH = "onyx_storage.json"



### RUN EVERY 5 HOURS ###

# =====================================================
# SYNC CAMOUFOX WORKER (SESSION-AWARE)
# =====================================================
def camoufox_login(proxy, email, password):
    with Camoufox(
        headless=True,
        proxy=proxy,
        geoip=True,
    ) as browser:

        context = browser.new_context(
            storage_state=STORAGE_PATH if os.path.exists(STORAGE_PATH) else None
        )
        page = context.new_page()

        # -----------------------------
        # Go to app root
        # -----------------------------
        page.goto("https://app.onyxodds.com/login")
        time.sleep(2.5)

        # -----------------------------
        # Check if already logged in
        # -----------------------------
        if "login" not in page.url:
            print("[ONYX] Reused existing session")
        else:
            print("[ONYX] Session expired — performing login")

            # -----------------------------
            # Fill email
            # -----------------------------
            page.focus('input[name="email"]')
            page.fill('input[name="email"]', email)
            time.sleep(random.uniform(0.4, 0.7))

            page.focus('input[name="password"]')
            time.sleep(random.uniform(0.4, 0.7))

            # -----------------------------
            # Fill password
            # -----------------------------
            page.fill('input[name="password"]', password)
            time.sleep(random.uniform(0.5, 0.9))

            page.mouse.click(50, 50)
            time.sleep(0.6)

            sign_button = page.locator('button[type="submit"]')

            # -----------------------------
            # LOGIN ATTEMPTS
            # -----------------------------
            for attempt in range(5):
                print(f"[ONYX] Login attempt {attempt + 1}")

                page.mouse.move(
                    random.randint(200, 600),
                    random.randint(200, 500)
                )
                time.sleep(0.4)

                sign_button.click()
                time.sleep(1.8)

                try:
                    page.wait_for_url(
                        "https://app.onyxodds.com/",
                        timeout=7_000
                    )
                    print("[ONYX] Login successful")
                    break
                except:
                    print("[ONYX] Login failed, retrying...")
                    page.bring_to_front()
                    time.sleep(2.5)
            else:
                page.screenshot("onyx_login_failed.png", full_page=True)
                raise RuntimeError("Onyx login failed")

            # -----------------------------
            # SAVE SESSION STATE (KEY LINE)
            # -----------------------------
            context.storage_state(path=STORAGE_PATH)
            print("[ONYX] Storage state saved")

        # -----------------------------
        # Fetch auth token
        # -----------------------------
        response = page.request.get(
            "https://app.onyxodds.com/api/auth/session"
        )

        if response.status != 200:
            print("[ONYX] Session fetch failed:", response.status)
            return None

        data = response.json()
        return data.get("user", {}).get("accessToken")


# =====================================================
# ASYNC SCHEDULER
# =====================================================
class OnyxAuth(BaseScheduler):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(
        self,
        session: aiohttp.ClientSession,
        redis_instance: RedisAsyncManager
    ):
        raw_proxy = os.getenv("ONYX_PROXY")
        if not raw_proxy:
            create_sentry_message(
                tag_key="onyx",
                tag_value="proxy_failure",
                message="No proxy found",
                level="error"
            )
            return

        host, port, user, password = raw_proxy.split(":")
        proxy = {
            "server": f"http://{host}:{port}",
            "username": user,
            "password": password,
        }

        auth_token = await asyncio.to_thread(
            camoufox_login,
            proxy,
            os.getenv("ONYX_EMAIL"),
            os.getenv("ONYX_PASSWORD"),
        )

        if not auth_token:
            create_sentry_message(
                tag_key="onyx",
                tag_value="auth_failure",
                message="Auth token not retrieved",
                level="error"
            )
            return

        await redis_instance.store_data(
            key_name="onyx_auth_token",
            data_to_store=auth_token,
            key_expiration=21600  # 6 hours
        )

        print("[ONYX] Auth token refreshed successfully")


# =====================================================
# ENTRYPOINT
# =====================================================
if __name__ == "__main__":
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
