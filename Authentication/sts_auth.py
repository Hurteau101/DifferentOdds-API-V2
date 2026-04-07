import os

from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
from curl_cffi import AsyncSession as CurlAsyncSession
from bs4 import BeautifulSoup

class STSAuth(BaseScheduler):
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.SPOOF)
        self.common_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Priority': 'u=0, i',
            'TE': 'trailers'
        }

    async def _get_view_states(self, session: CurlAsyncSession) -> dict:
        """Extracts the necessary view state values from the login page to prepare for authentication."""
        def find_values(name: str, soup: BeautifulSoup):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""

        url = "https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx"


        response = await session.get(url=url, headers={
            **self.common_headers,
            'Referer': 'https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx',
        })
        soup = BeautifulSoup(response.text, "html.parser")

        return {
            "__VIEWSTATE": find_values("__VIEWSTATE", soup),
            "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR", soup),
            "__EVENTVALIDATION": find_values("__EVENTVALIDATION", soup),
        }

    async def run_scheduler(self, session: CurlAsyncSession, redis_instance):
        username = os.getenv("STG_USERNAME")
        password = os.getenv("STG_PASSWORD")

        if not username or not password:
            raise ValueError("STS_USERNAME and STS_PASSWORD must be set in the environment variables.")

        view_state_payload = await self._get_view_states(session=session)

        if not view_state_payload:
            return

        login_payload = {
            **view_state_payload,
            "txtAccessOfCode": username,
            "txtAccessOfPassword": password,
            "button": ""
        }

        await session.post(headers={
            **self.common_headers,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://bettheguys.com',
            'Referer': 'https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx',
        }, url="https://bettheguys.com/Login.aspx", data=login_payload)

        cookies = dict(session.cookies)

        if cookies:
            await redis_instance.store_data(
                key_name="sts_cookies",
                data_to_store=cookies,
                key_expiration=1200  # 20 Minutes
            )


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sts = STSAuth()
            await sts.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())