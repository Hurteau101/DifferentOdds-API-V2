import os
from itertools import cycle
from typing import Union
from curl_cffi import AsyncSession as CurlAsyncSession
from aiohttp import ClientSession as AiohttpClientSession
from Monitoring.monitoring import create_sentry_message


class ProxyManager:
    def __init__(self, api_caller_func, proxies=None):
        self.proxies = proxies
        if not proxies:
            self.proxies = os.getenv("PROXIES").split(",") if os.getenv("PROXIES") else ""

        self.proxy_amount = len(self.proxies)
        self.proxy_pool = cycle(self.proxies)
        self.api_caller = api_caller_func

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
        for i in range(self.proxy_amount):
            proxy = self._cycle_proxies()
            if proxy:
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

                    if not api_data:
                        continue

                    return api_data
                except Exception:
                    continue

        create_sentry_message(
            tag_key="proxy",
            tag_value="all_proxies_failed",
            message=f"All proxies failed for {book_name}",
            level="error"
        )

        return None