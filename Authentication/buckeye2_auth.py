import os
from dotenv import load_dotenv
from APScheduler.base_scheduler import BaseScheduler
from curl_cffi import AsyncSession as CurlAsyncSession


class Buckeye2Auth(BaseScheduler):
    URL = "https://www.247bettor.com/cloud/api/System/authenticateCustomer"
    load_dotenv()

    def __init__(self):
        super().__init__()

    # async def run_scheduler(self, session, redis_instance) -> bool:
    #     username = os.getenv("BUCKEYE_2_USERNAME")
    #     password = os.getenv("BUCKEYE_2_PASSWORD")
    #
    #     if not username or not password:
    #         raise ValueError("Missing required environment variables: BUCKEYE_2_USERNAME, BUCKEYE_2_PASSWORD")
    #
    #     proxies = os.environ.get("RESIDENTIAL_PROXIES")
    #     if not proxies:
    #         raise ValueError("Missing required environment variables: RESIDENTIAL_PROXIES")
    #
    #     for proxy in proxies.split(","):
    #         split_proxy = proxy.split(":")
    #         ip, port, proxy_user, proxy_pass = split_proxy
    #         proxy_url = f"http://{proxy_user}:{proxy_pass}@{ip}:{port}"
    #
    #         try:
    #             async with AsyncSession(impersonate="firefox") as curl_session:
    #
    #                 # Get cf_clearance cookie
    #                 await curl_session.get(
    #                     "https://www.247bettor.com/",
    #                     proxy=proxy_url,
    #                     headers={
    #                         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    #                         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    #                         "Accept-Language": "en-US,en;q=0.9",
    #                         "Accept-Encoding": "gzip, deflate, br, zstd",
    #                         "Connection": "keep-alive",
    #                         "Sec-Fetch-Dest": "document",
    #                         "Sec-Fetch-Mode": "navigate",
    #                         "Sec-Fetch-Site": "none",
    #                     }
    #                 )
    #
    #                 response = await curl_session.post(
    #                     url=Buckeye2Auth.URL,
    #                     proxy=proxy_url,
    #                     data={
    #                         "customerID": username,
    #                         "state": "true",
    #                         "password": password,
    #                         "multiaccount": "1",
    #                         "response_type": "code",
    #                         "client_id": username,
    #                         "domain": "247bettor.com",
    #                         "redirect_uri": "247bettor.com",
    #                         "operation": "authenticateCustomer",
    #                         "RRO": "1",
    #                     },
    #                     headers={
    #                         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    #                         "Accept": "*/*",
    #                         "Accept-Language": "en-US,en;q=0.9",
    #                         "Accept-Encoding": "gzip, deflate, br, zstd",
    #                         "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    #                         "Authorization": "Bearer undefined",
    #                         "X-Requested-With": "XMLHttpRequest",
    #                         "Origin": "https://www.247bettor.com",
    #                         "Referer": "https://www.247bettor.com/",
    #                         "Connection": "keep-alive",
    #                         "Sec-Fetch-Dest": "empty",
    #                         "Sec-Fetch-Mode": "cors",
    #                         "Sec-Fetch-Site": "same-origin",
    #                         "Priority": "u=0",
    #                         "TE": "trailers",
    #                     }
    #                 )
    #
    #
    #                 if response.status_code != 200:
    #                     continue
    #
    #                 token_data = response.json()
    #
    #                 if not (isinstance(token_data, dict) and "code" in token_data):
    #                     continue
    #
    #                 auth_token = token_data.get("code")
    #
    #                 await redis_instance.store_data(
    #                     key_name="buckeye_2_auth_token",
    #                     data_to_store=auth_token,
    #                     key_expiration=1200  # 20 minutes
    #                 )
    #
    #                 return True
    #
    #         except Exception as e:
    #             continue
    #
    #     return False

    async def run_scheduler(self, session, redis_instance) -> bool:
        username = os.getenv("BUCKEYE_2_USERNAME")
        password = os.getenv("BUCKEYE_2_PASSWORD")

        if not username or not password:
            raise ValueError("Missing required environment variables: BUCKEYE_2_USERNAME, BUCKEYE_2_PASSWORD")

        # await self.api_caller(
        #     url="https://www.247bettor.com/",
        #     method="GET",
        #     use_proxy=True,
        #     parse_text=True,
        # )

        response = await self.api_caller(
            url=Buckeye2Auth.URL,
            use_proxy=True,
            method="POST",
            parse_text=True,
            json={
                "customerID": username,
                "state": "true",
                "password": password,
                "multiaccount": "1",
                "response_type": "code",
                "client_id": username,
                "domain": "247bettor.com",
                "redirect_uri": "247bettor.com",
                "operation": "authenticateCustomer",
                "RRO": "1",
            },
            headers={
                "Authorization": "Bearer undefined",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://www.247bettor.com",
                "Referer": "https://www.247bettor.com/",
                "TE": "trailers",
            }
        )

        if not (isinstance(response, dict) and "code" in response):
            return False

        auth_token = response.get("code")

        await redis_instance.store_data(
            key_name="buckeye_2_auth_token",
            data_to_store=auth_token,
            key_expiration=1200  # 20 minutes
        )

        return True





if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    async def main():
        redis_instance = RedisAsyncManager(database=5)
        buckeye_2 = Buckeye2Auth()
        async with CurlAsyncSession(impersonate="firefox") as session:
            await buckeye_2.run_scheduler(session=session, redis_instance=redis_instance)
            await redis_instance.close_for_shutdown()

    asyncio.run(main())