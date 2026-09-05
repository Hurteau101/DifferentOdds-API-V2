import os
from playwright.async_api import async_playwright
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Utils.request_caller import PredefinedProxy


class CaesarAuth(AuthBase):
    _BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

    def __init__(self):
        super().__init__(book_name="caesars", category="sgp")

    async def _block_heavy_resources(self, route):
        request = route.request

        if request.frame.parent_frame is not None:
            await route.abort()
            return

        if request.resource_type in self._BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return

        await route.continue_()

    async def extract_token(self, use_session: bool=True, session_length:int=13) -> str | None:
        proxy_list = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value
        if not proxy_list:
            raise ValueError("No proxies available.")

        async with async_playwright() as p:
            for proxy in proxy_list:
                proxy_parts = self.split_colon_at_proxy(proxy)

                if not proxy_parts:
                    continue

                proxy_dict = {
                    "server": f"http://{proxy_parts[2]}:{proxy_parts[3]}",
                    "username": proxy_parts[0],
                    "password": proxy_parts[1]
                }

                browser = await p.chromium.launch(headless=False)

                try:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        proxy=proxy_dict
                    )

                    await context.route("**/*", self._block_heavy_resources)

                    page = await context.new_page()

                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)

                    await page.goto("https://sportsbook.caesars.com/us/az/bet/", wait_until="networkidle")
                    await page.wait_for_timeout(5000) # Wait for any JS challenges to finish.

                    for _ in range(10):
                        cookies = await context.cookies()
                        waf_token = next((c["value"] for c in cookies if c["name"] == "aws-waf-token"), None)

                        if waf_token:
                            print(waf_token)
                            return waf_token

                        await page.wait_for_timeout(500)

                except Exception as e:
                    pass

                finally:
                    await browser.close()

            return None

    async def run_auth(self) -> bool:
        if os.name != 'nt':
            os.environ['DISPLAY'] = ':99'

        waf_token = await self.extract_token()

        if waf_token:
            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store=waf_token,
                expiration_time=self.pre_calculated_redis_expiration
            )

            return True

        insert_log(
            book_name=self.book_data.title,
            error_type=ErrorTypes.AUTH,
            error_message="All proxies failed, could not extract auth"
        )

        return False


if __name__ == "__main__":
    import asyncio
    caesar = CaesarAuth()
    asyncio.run(caesar.run_auth())
