from playwright.sync_api import sync_playwright
from Redis.redis_manager import RedisSync
import time
from Discord_Logger.discord_log import DiscordLog

import logging

# logging.basicConfig(
#     filename="/home/administrator/caesar_auth.log",
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s"
# )

logging.info("Starting Caesars WAF token fetch")

def get_waf_token(
    redis_client: RedisSync,
    ttl: int = 600,
    max_retries: int = 5,
    retry_delay: float = 0.5,
) -> bool:

    for attempt in range(max_retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = browser.new_context()
                page = context.new_page()

                page.goto(
                    "https://sportsbook.caesars.com/us/az/bet/",
                    wait_until="networkidle"
                )

                page.locator(
                    "//div[normalize-space()='Betslip']"
                ).wait_for(state="visible", timeout=120000)

                cookies = context.cookies()
                waf_token = next(
                    (c["value"] for c in cookies if c["name"] == "aws-waf-token"),
                    None
                )

                if waf_token:
                    redis_client.set(
                        "caesars_sgp_waf_token",
                        waf_token,
                        ex=ttl
                    )

                    return True

        except Exception:
            logging.exception(
                f"Attempt {attempt + 1}/{max_retries} failed while fetching WAF token"
            )

        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

        time.sleep(retry_delay)

    logging.info("Finished Logging Caesars WAF token fetch")
    return False

if __name__ == "__main__":
    redis_client = RedisSync(db=5)
    waf_token = get_waf_token(redis_client)
    if not waf_token:
        discord_logger = DiscordLog(channel_name="auth")

        discord_logger.send_logger(
            log_name="Caesars WAF Token Retrieval Failed",
            log_message="WAF token not found after maximum retries.",
            key_name="caesars_auth",
            role_name="caesars",
            key_value="error",
            key_expiration=300
        )

#
# from playwright.sync_api import sync_playwright, TimeoutError
# import time
# import logging
#
# from Discord_Logger.discord_log import DiscordLog
# from Redis.redis_manager import RedisSync
#
#
# def get_waf_token(
#     redis_client,
#     ttl: int = 600,
#     max_retries: int = 5,
#     retry_delay: float = 2.0,
# ) -> bool:
#
#     for attempt in range(max_retries):
#         logging.info(f"Caesars WAF attempt {attempt + 1}/{max_retries}")
#
#         try:
#             with sync_playwright() as p:
#                 browser = p.chromium.launch(
#                     headless=True,
#                     args=[
#                         "--disable-blink-features=AutomationControlled",
#                         "--no-sandbox",
#                         "--disable-dev-shm-usage",
#                     ],
#                 )
#
#                 context = browser.new_context(
#                     user_agent=(
#                         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                         "AppleWebKit/537.36 (KHTML, like Gecko) "
#                         "Chrome/121.0.0.0 Safari/537.36"
#                     )
#                 )
#
#                 page = context.new_page()
#
#                 page.goto(
#                     "https://sportsbook.caesars.com/us/az/bet/",
#                     wait_until="domcontentloaded",
#                     timeout=120_000,
#                 )
#
#                 start = time.time()
#                 waf_token = None
#
#                 while time.time() - start < 90:
#                     cookies = context.cookies()
#                     waf_token = next(
#                         (c["value"] for c in cookies if c["name"] == "aws-waf-token"),
#                         None,
#                     )
#
#                     if waf_token:
#                         break
#
#                     time.sleep(1)
#
#                 if not waf_token:
#                     continue
#
#                 redis_client.set(
#                     "caesars_sgp_waf_token",
#                     waf_token,
#                     ex=ttl,
#                 )
#
#                 logging.info("Successfully stored Caesars WAF token")
#                 return True
#
#         except Exception:
#             logging.exception("Failed to fetch Caesars WAF token")
#
#         finally:
#             try:
#                 context.close()
#                 browser.close()
#             except Exception:
#                 pass
#
#         time.sleep(retry_delay)
#
#     return False
#
#
# if __name__ == "__main__":
#     redis_client = RedisSync(db=5)
#     waf_token = get_waf_token(redis_client)
#     if not waf_token:
#         discord_logger = DiscordLog(channel_name="auth")
#
#         discord_logger.send_logger(
#             log_name="Caesars WAF Token Retrieval Failed",
#             log_message="WAF token not found after maximum retries.",
#             key_name="caesars_auth",
#             role_name="caesars",
#             key_value="error",
#             key_expiration=300
#         )
