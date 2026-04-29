import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from Utils.request_caller import SportbookRequestType
import aiohttp


class Buckeye2Auth(BaseScheduler):
    URL = "https://wwcd.me/cloud/api/System/authenticateCustomer"
    load_dotenv()

    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC)

    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance) -> bool:
        username=os.getenv("BUCKEYE_2_USERNAME")
        password=os.getenv("BUCKEYE_2_PASSWORD")

        if not username or not password:
            raise ValueError("Missing required environment variables: BUCKEYE_2_USERNAME, BUCKEYE_2_PASSWORD")

        proxies = os.environ.get("RESIDENTIAL_PROXIES")
        if not proxies:
            raise ValueError("Missing required environment variables: RESIDENTIAL_PROXIES")


        for proxy in proxies.split(","):
            split_proxy = proxy.split(":")

            ip, port, proxy_user, proxy_pass = split_proxy
            proxy_url = f"http://{proxy_user}:{proxy_pass}@{ip}:{port}"

            response = await session.post(
                url=Buckeye2Auth.URL,
                data={
                    "customerID": username,
                    "password": password,
                },
                proxy=proxy_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://betvegas23.com/",
                    "Origin": "https://betvegas23.com",
                })

            if response.status != 200:
                continue

            token_data = await response.json()

            if not (isinstance(token_data, dict) and "code" in token_data):
                continue

            auth_token = token_data.get("code")

            await redis_instance.store_data(
                key_name="buckeye_2_auth_token",
                data_to_store=auth_token,
                key_expiration=1200 # 20 Minutes
            )

            return True

        return False


if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager
    import aiohttp

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        async with aiohttp.ClientSession() as session:
            buckeye_2 = Buckeye2Auth()
            await buckeye_2.run_scheduler(session=session, redis_instance=redis_instance)
        await redis_instance.close_for_shutdown()

    asyncio.run(main())