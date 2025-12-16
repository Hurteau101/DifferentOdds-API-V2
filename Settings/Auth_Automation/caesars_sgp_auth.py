from playwright.sync_api import sync_playwright
from Redis.redis_manager import RedisSync
import time

import logging

logging.basicConfig(
    filename="/home/administrator/caesar_auth.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)



logging.info("Starting Caesars WAF token fetch")

def get_waf_token(
    redis_client: RedisSync,
    ttl: int = 600,
    max_retries: int = 5,
    retry_delay: float = 0.5,
) -> str | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        try:
            context = browser.new_context()
            page = context.new_page()

            page.goto(
                "https://sportsbook.caesars.com/us/az/bet/",
                wait_until="networkidle"
            )
            page.screenshot(path="debug.png", full_page=True)
            page.locator("//div[normalize-space()='Betslip']").wait_for(state="visible", timeout=120000)

            for _ in range(max_retries):
                cookies = context.cookies()
                waf_token = next(
                    (c["value"] for c in cookies if c["name"] == "aws-waf-token"),
                    None
                )

                if waf_token:
                    logging.info("WAF token stored in Redis")
                    redis_client.set(
                        "caesars_sgp_waf_token",
                        waf_token,
                        ex=ttl
                    )

                    return None

                time.sleep(retry_delay)

            logging.warning("Failed to obtain WAF token")
            return None

        finally:
            browser.close()

if __name__ == "__main__":
    redis_client = RedisSync(db=5)
    get_waf_token(redis_client)

