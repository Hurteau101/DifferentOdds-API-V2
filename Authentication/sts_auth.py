import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
from camoufox.async_api import AsyncCamoufox

class STSAuth(BaseScheduler):
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.SPOOF)

    async def run_scheduler(self, redis_instance, **kwargs):
        username = os.getenv("STS_USERNAME")
        password = os.getenv("STS_PASSWORD")
        proxy_list = os.getenv("RESIDENTIAL_PROXIES", "").split(",")

        if not username or not password:
            raise ValueError("STS_USERNAME and STS_PASSWORD must be set.")

        # Used for Linux. Need to run this non-headless.
        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'


        for proxy in proxy_list:
            parts = proxy.strip().split(":")
            ip, port, user, pw = parts[0], parts[1], parts[2], parts[3]

            try:
                async with AsyncCamoufox(
                    headless=False,
                    geoip=True,
                    proxy={
                        "server": f"http://{ip}:{port}",
                        "username": user,
                        "password": pw
                    }
                ) as browser:
                    context = await browser.new_context()
                    page = await context.new_page()

                    await page.goto("https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx", wait_until="networkidle")
                    await page.fill("input[name='txtAccessOfCode']", username)
                    await page.fill("input[name='txtAccessOfPassword']", password)
                    await page.click("input[name='button']")
                    await page.wait_for_url("**/Player/main.aspx", timeout=15000)

                    cookies = {c["name"]: c["value"] for c in await context.cookies()}

                    if not cookies.get("ASP.NET_SessionId") or not cookies.get(".AITQKIAUT"):
                        print(f"Proxy {ip}:{port} - missing required cookies, trying next.")
                        continue

                    await redis_instance.store_data(key_name="sts_cookies", data_to_store=cookies, key_expiration=1200)
                    await redis_instance.store_data(key_name="sts_proxy", data_to_store=proxy, key_expiration=1200)
                    return

            except Exception as e:
                print(f"Proxy {ip}:{port} failed: {e}, trying next.")
                continue

        raise RuntimeError("Failed to authenticate with all provided proxies.")


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        sts = STSAuth()
        await sts.run_scheduler(redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())