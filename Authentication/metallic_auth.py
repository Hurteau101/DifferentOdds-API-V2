import os
from dotenv import load_dotenv
from multidict import CIMultiDictProxy
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
import aiohttp


class MetallicAuth(BaseScheduler):
    LOGIN_URL = "https://black34.com/player-api/identity/CustomerLoginRedir?RedirToHome=1"
    FORM_URL = "https://black34.com/player-api/identity/customerLoginFromToken"
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    # This handles the login redirect, where it will point to the location, that has the temp token we need.
    async def login_redirect(self, session: aiohttp.ClientSession):
        username = os.getenv("METALLIC_USERNAME")
        password = os.getenv("METALLIC_PASSWORD")

        if not username or not password:
            raise ValueError("Missing required environment variables: METALLIC_USERNAME, METALLIC_PASSWORD")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://black34.com',
            'Connection': 'keep-alive',
            'Referer': 'https://black34.com/',
            'Upgrade-Insecure-Requests': '1',
        }

        async with session.post(url=self.LOGIN_URL, headers=headers, allow_redirects=False, data={
            "customerid": username,
            "password": password,
            "submit": "Sign In"
        }) as response:
            headers = response.headers
            if response.status != 302 or not isinstance(headers, CIMultiDictProxy):
                return None

            location = headers.get('Location', '')

            return location.split('t=')[-1] if "t=" in location else None

    async def get_auth(self, session: aiohttp.ClientSession, temp_token: str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': 'https://black34.com',
            'Referer': 'https://black34.com/v2/'
        }

        async with session.post(url=self.FORM_URL, headers=headers, json={
            "token": temp_token,
            "version": "1.3.47"
        }) as response:
            if response.status != 200:
                return None

            token_data = await response.json()

            if not isinstance(token_data, dict) or "AccessToken" not in token_data:
                return None

            return token_data["AccessToken"]

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance):
        temp_token = await self.login_redirect(session)

        if not temp_token:
            return

        auth_token = await self.get_auth(session, temp_token)

        if not auth_token:
            return

        await redis_instance.store_data(
            key_name="metallic_token",
            data_to_store=auth_token,
            key_expiration=5400 # 90 Minutes
        )


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            metallic = MetallicAuth()
            await metallic.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())