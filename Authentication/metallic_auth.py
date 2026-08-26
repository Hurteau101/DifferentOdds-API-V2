import os

import curl_cffi
from dotenv import load_dotenv
from multidict import CIMultiDictProxy
from curl_cffi import AsyncSession as CurlAsyncSession

from Authentication.base_auth import BaseAuth


class MetallicAuth(BaseAuth):
    LOGIN_URL = "https://black34.com/player-api/identity/CustomerLoginRedir?RedirToHome=1"
    FORM_URL = "https://black34.com/player-api/identity/customerLoginFromToken"
    load_dotenv()

    def __init__(self):
        super().__init__(book_name="metallic", category="sportsbooks")

    # This handles the login redirect, where it will point to the location, that has the temp token we need.
    async def login_redirect(self, session: CurlAsyncSession):
        username = os.getenv("METALLIC_USERNAME")
        password = os.getenv("METALLIC_PASSWORD")

        if not username or not password:
            raise ValueError("Missing required environment variables: METALLIC_USERNAME, METALLIC_PASSWORD")

        headers = {
            'Origin': 'https://black34.com',
            'Connection': 'keep-alive',
            'Referer': 'https://black34.com/',
            'Upgrade-Insecure-Requests': '1',
        }

        response = await session.post(
            url=self.LOGIN_URL,
            headers=headers,
            allow_redirects=False,
            data={
                "customerid": username,
                "password": password,
                "submit": "Sign In"
            }
        )

        resp_headers = response.headers

        if response.status_code != 302 or not isinstance(resp_headers, curl_cffi.requests.headers.Headers):
            return None

        location = resp_headers.get('Location', '')
        return location.split('t=')[-1] if "t=" in location else None

    async def get_auth(self, session: CurlAsyncSession, temp_token: str):
        headers = {
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            # 'Accept': 'application/json, text/plain, */*',
            # 'Content-Type': 'application/json',
            'Origin': 'https://black34.com',
            'Referer': 'https://black34.com/v2/'
        }

        response = await self.api_caller(
            session=session,
            url=self.FORM_URL,
            method="POST",
            headers=headers,
            json={
                "token": temp_token,
                "version": "1.3.47"
            }
        )

        if not isinstance(response, dict) or "AccessToken" not in response:
            return None

        return response["AccessToken"]


    async def run_scheduler(self, session: CurlAsyncSession, redis_instance) -> bool:
        temp_token = await self.login_redirect(session)

        if not temp_token:
            return False

        auth_token = await self.get_auth(session, temp_token)

        if not auth_token:
            return False

        await redis_instance.store_data(
            key_name=self.auth_id_name,
            data_to_store=auth_token,
            key_expiration=5400 # 90 Minutes
        )

        return True


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager


    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with CurlAsyncSession(impersonate="chrome") as session:
            metallic = MetallicAuth()
            await metallic.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())