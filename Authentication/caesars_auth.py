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

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        # PROXY SELLER
        proxy = os.getenv("RES_PROXY")
        if not proxy:
            create_sentry_message(
                tag_key="caesars",
                tag_value="proxy_failure",
                message="No proxy found",
                level="error"
            )
            return

        # proxies = [proxy]
        proxies = proxy.split(",")
        print(proxies)
        async with async_playwright() as play:  # ← start once
            for attempt in range(CaesarAuth.MAX_RETRY):
                for proxy in proxies:
                    user, password, host, port = proxy.split(":")
                    # host, port, user, password = proxy.split(":")

                    browser = None

                    try:
                        browser = await play.chromium.launch(
                            headless=True,
                            proxy={
                                "server": f"http://{host}:{port}",
                                "username": user,
                                "password": password,
                            },
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--start-maximized"
                            ]
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

                        print(waf_token)

                        if waf_token:
                            await redis_instance.store_data(
                                key_name="caesars_waf_token",
                                data_to_store=waf_token,
                                key_expiration=720
                            )
                            return

                    except Exception as e:
                        create_sentry_message(
                            tag_key="caesars",
                            tag_value="Exception",
                            message=str(e),
                            level="error"
                        )

                        continue

                    finally:
                        if browser:
                            await browser.close()

                await asyncio.sleep(CaesarAuth.RETRY_DELAY)

        create_sentry_message(
            tag_key="caesars",
            tag_value="auth_failure",
            message="WAF token not found after authentication attempts.",
            level="error"
        )

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









# import asyncio
# import os
# import time
#
# import aiohttp
# from dotenv import load_dotenv
# from playwright.async_api import async_playwright
# from APScheduler.base_scheduler import BaseScheduler
# from Monitoring.monitoring import create_sentry_message
# from Redis.redis_manager import RedisAsyncManager
# from Utils.request_caller import SportbookRequestType
#
# class CaesarAuth(BaseScheduler):
#     load_dotenv()
#     MAX_RETRY = 2
#     RETRY_DELAY = 0.5
#     def __init__(self):
#         super().__init__(request_type=SportbookRequestType.ASYNC)
#
#     async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
#         raw_proxy_string = os.getenv("CAESARS_PROXY")
#         if not raw_proxy_string:
#             create_sentry_message(
#                 tag_key="caesars",
#                 tag_value="proxy_failure",
#                 message="No proxy found",
#                 level="error"
#             )
#             return
#
#         proxies = raw_proxy_string.split(",")
#
#         async with async_playwright() as play:  # ← start once
#             for attempt in range(CaesarAuth.MAX_RETRY):
#                 for proxy in proxies:
#                     host, port, user, password = proxy.split(":")
#
#                     browser = None
#
#                     try:
#                         browser = await play.chromium.launch(
#                             headless=True,
#                             proxy={
#                                 "server": f"http://{host}:{port}",
#                                 "username": user,
#                                 "password": password,
#                             },
#                             args=[
#                                 "--disable-blink-features=AutomationControlled",
#                                 "--start-maximized"
#                             ]
#                         )
#
#                         context = await browser.new_context()
#                         page = await context.new_page()
#
#                         await page.goto(
#                             "https://sportsbook.caesars.com/us/az/bet/",
#                             wait_until="networkidle"
#                         )
#
#                         await page.locator(
#                             "//div[normalize-space()='Betslip']"
#                         ).wait_for(state="visible", timeout=120_000)
#
#                         cookies = await context.cookies()
#
#                         waf_token = next(
#                             (cookie["value"] for cookie in cookies if cookie["name"] == "aws-waf-token"),
#                             None
#                         )
#
#                         if waf_token:
#                             await redis_instance.store_data(
#                                 key_name="caesars_waf_token",
#                                 data_to_store=waf_token,
#                                 key_expiration=720
#                             )
#                             return
#
#                     except Exception as e:
#                         create_sentry_message(
#                             tag_key="caesars",
#                             tag_value="Exception",
#                             message=str(e),
#                             level="error"
#                         )
#
#                         return
#
#                     finally:
#                         if browser:
#                             await browser.close()
#
#                 await asyncio.sleep(CaesarAuth.RETRY_DELAY)
#
#         create_sentry_message(
#             tag_key="caesars",
#             tag_value="auth_failure",
#             message="WAF token not found after authentication attempts.",
#             level="error"
#         )
#
# if __name__ == "__main__":
#     import asyncio
#     from Redis.redis_manager import RedisAsyncManager
#     import aiohttp
#
#     redis_instance = RedisAsyncManager(database=5)
#     caesar = CaesarAuth()
#     async def main():
#         async with aiohttp.ClientSession() as session:
#             await caesar.run_scheduler(session, redis_instance)
#
#     asyncio.run(main())