import os
from camoufox.async_api import AsyncCamoufox
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Utils.request_caller import PredefinedProxy
from loguru import logger


class STSAuth(AuthBase):
    def __init__(self):
        super().__init__(book_name="sts", category="sportsbooks")

    async def run_auth(self) -> bool:
        sts_username = os.getenv("STS_USERNAME")
        sts_password = os.getenv("STS_PASSWORD")
        proxy_list = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value

        if not sts_username or not sts_password:
            raise ValueError("STS_USERNAME and STS_PASSWORD must be set.")

        for proxy in proxy_list:
            proxy_parts = self.split_colon_at_proxy(proxy)

            if not proxy_parts:
                continue

            username, password, ip, port = proxy_parts

            try:
                async with AsyncCamoufox(
                    headless=False,
                    geoip=True,
                    proxy={
                        "server": f"http://{ip}:{port}",
                        "username": username,
                        "password": password
                    }
                ) as browser:
                    context = await browser.new_context()
                    page = await context.new_page()

                    await page.goto("https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx", wait_until="networkidle", timeout=20000)
                    await page.fill("input[name='txtAccessOfCode']", sts_username)
                    await page.fill("input[name='txtAccessOfPassword']", sts_password)
                    await page.click("input[name='button']")
                    await page.wait_for_url("**/Player/main.aspx", timeout=15000)

                    cookies = {c["name"]: c["value"] for c in await context.cookies()}

                    if not cookies.get("ASP.NET_SessionId") or not cookies.get(".AITQKIAUT"):
                        logger.error(f"Proxy {ip}:{port} - missing required cookies, trying next.")
                        continue

                    await self.store_data(key_name=self.auth_id_name, data_to_store=cookies, expiration_time=1200)
                    await self.store_data(key_name="sts_proxy", data_to_store=proxy, expiration_time=1200)
                    return True

            except Exception as e:
                logger.error(f"Proxy {ip}:{port} failed: {e}, trying next.")
                continue


        insert_log(
            book_name=self.book_data.title,
            error_type=ErrorTypes.AUTH,
            error_message="All proxies failed, could not extract auth"
        )

        return False

if __name__ == "__main__":
    import asyncio
    sts = STSAuth()
    asyncio.run(sts.run_auth())
