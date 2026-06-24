import asyncio
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

load_dotenv()

USER_DATA_DIR = r"C:\cdp-profile" if os.name == "nt" else "/home/administrator/cdp-profile"
CDP_PORT = 9222
REFRESH_INTERVAL = 5 * 60


RAW_PROXY = os.getenv("DRAFTKINGS_PROXY")

if not RAW_PROXY:
    raise ValueError("Missing required environment variable: DRAFTKINGS_PROXY")

split_proxy = RAW_PROXY.split(":")

PROXY = {
    "server": f"http://{split_proxy[0]}:{split_proxy[1]}",
    "username": split_proxy[2],
    "password": split_proxy[3],
}

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            channel="chrome",
            proxy=PROXY,
            args=[f"--remote-debugging-port={CDP_PORT}", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://sportsbook.draftkings.com/",
                        wait_until="domcontentloaded", timeout=60000)
        print(f"Browser up. CDP on http://127.0.0.1:{CDP_PORT}", flush=True)

        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            await page.reload(wait_until="domcontentloaded")


asyncio.run(main())