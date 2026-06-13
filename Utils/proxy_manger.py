import asyncio
import os
from itertools import cycle
from typing import Union
from curl_cffi import AsyncSession as CurlAsyncSession
from aiohttp import ClientSession as AiohttpClientSession
from dotenv import load_dotenv
from Monitoring.monitoring import create_sentry_message

load_dotenv()

class ProxyManager:
    def __init__(self, api_caller_func, proxies=None):
        self.proxies = proxies
        if not proxies:
            self.proxies = os.getenv("RESIDENTIAL_PROXIES").split(",") if os.getenv("RESIDENTIAL_PROXIES") else ""

        self.proxy_amount = len(self.proxies)
        self.proxy_pool = cycle(self.proxies)
        self.api_caller = api_caller_func


    async def rotating_proxy_caller(
            self,
            book_name: str,
            session: Union[CurlAsyncSession, AiohttpClientSession],
            url: str,
            method: str,
            headers: dict | None = None,
            payload: dict | None = None,
            parse_json: bool = False,
            params: dict | None = None,
            max_retries: int = 5,
    ):
        """Attempt to call the API using Floppydata rotating proxy, retrying on failure."""
        connection_url = os.getenv("FLOPPYDATA_PROXY_URL")
        if not connection_url:
            create_sentry_message(
                tag_key="proxy",
                tag_value="proxy_failure",
                message="FLOPPYDATA_PROXY_URL environment variable is not set.",
                level="error"
            )

            return None

        for attempt in range(max_retries):
            try:
                api_data = await self.api_caller(
                    book_name=book_name,
                    session=session,
                    url=url,
                    method=method,
                    proxy=connection_url,
                    headers=headers,
                    params=params,
                    payload=payload,
                    parse_json=parse_json
                )

                return api_data

                # if api_data:
                #     return api_data

            except Exception as e:
                print(e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue

        create_sentry_message(
            tag_key="proxy",
            tag_value="all_proxies_failed",
            message=f"All proxy attempts failed for {book_name}",
            level="error"
        )

        print(f"All proxies failed for {book_name}")
        return None


    def _cycle_proxies(self):
        """Get the next proxy from the pool."""
        proxy = next(self.proxy_pool)

        if not proxy:
            create_sentry_message(
                tag_key="proxy",
                tag_value="proxy_failure",
                message="No proxy found",
                level="error"
            )

            return None

        proxy_parts = proxy.split(":")
        ip, port, username, password = proxy_parts

        return f"http://{username}:{password}@{ip}:{port}"

    async def proxy_caller(
            self,
            book_name: str,
            session: Union[CurlAsyncSession, AiohttpClientSession],
            url: str,
            method: str,
            headers: dict | None = None,
            payload: dict | None = None,
            parse_json: bool = False,
            params: dict | None = None
    ):
        """Attempt to call the API using available proxies. Will try each proxy in the list until one works."""
        proxies_to_try = list(self.proxies)

        for proxy_raw in proxies_to_try:
            proxy_parts = proxy_raw.split(":")
            ip, port, username, password = proxy_parts
            proxy = f"http://{username}:{password}@{ip}:{port}"

            try:
                api_data = await self.api_caller(
                    book_name=book_name,
                    session=session,
                    url=url,
                    method=method,
                    proxy=proxy,
                    headers=headers,
                    params=params,
                    payload=payload,
                    parse_json=parse_json
                )

                if api_data:
                    return api_data

                # print(f"Failed with proxy {ip}, trying next...")

            except Exception as e:
                # print(f"Proxy {ip} raised: {e}, trying next...")
                continue

        create_sentry_message(
            tag_key="proxy",
            tag_value="all_proxies_failed",
            message=f"All proxies failed for {book_name}",
            level="error"
        )

        print(f"All proxies failed for {book_name}")
        return None