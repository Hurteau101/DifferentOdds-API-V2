import inspect
import json
import os
from enum import Enum
from typing import Union

import aiohttp
import sentry_sdk
from aiohttp import ClientResponse
from curl_cffi.requests import Response as CurlResponse
from curl_cffi import AsyncSession as CurlAsyncSession
from aiohttp import ClientSession as AiohttpClientSession
from discordwebhook import Discord
from dotenv import load_dotenv

from Monitoring.Discord_Logging.logger import send_discord_message
from cachetools import TTLCache


load_dotenv()

class SportbookRequestType(Enum):
    ASYNC = "async"
    SPOOF = "spoof"

class APICaller:
    """Class to handle outbound API requests for sportsbooks and handle there responses"""
    def __init__(self, request_type: SportbookRequestType, valid_status_codes: list[int] | None = None):
        self.valid_status_codes = valid_status_codes or [200, 201]
        self.request_type = request_type
        self._403_cache = TTLCache(maxsize=100, ttl=300)

        webhook = os.getenv("DISCORD_403_LOGGING_URL")

        self.discord = Discord(url=webhook) if webhook else None

    def check_403(self, status_code: int, book_name: str):
        if not self.discord or status_code != 403 or self._403_cache.get(book_name):
            return

        stack = inspect.stack()
        caller_class = stack[1][0].f_locals["self"].__class__.__name__

        send_discord_message(
            self.discord,
            severity=1,
            title=f"403 {book_name} Failure",
            description="A 403 status code was returned.",
            multiple_fields=True,
            fields=[
                {"name": "Class", "value": caller_class, "inline": False},
            ]
        )

        self._403_cache[book_name] = True

    async def api_caller(self,
                    book_name: str,
                    session: Union[CurlAsyncSession, AiohttpClientSession],
                    url: str,
                    method: str,
                    headers: dict | None = None,
                    proxy: dict | None = None,
                    payload: dict | str | list | None = None,
                    parse_json: bool = False,
                    params: dict | None =None
                    ) -> dict | list | None:
        """Fetch data from the API based on request type."""

        method = method.lower()
        if method not in ["get", "post"]:
            raise ValueError("Method must be 'get' or 'post'.")

        if self.request_type == SportbookRequestType.ASYNC:
            # Use the method type [POST or GET]
            async with getattr(session, method)(
                    url, headers=headers, proxy=proxy, params=params if method == "get" else None,
                    data=payload if isinstance(payload, str) else None,
                    json=payload if isinstance(payload, dict) or isinstance(payload, list) else None
            ) as response:
                return await self.handle_async_response(response, parse_json, book_name)

        # Use the method type [POST or GET]
        response = await getattr(session, method)(
            url, headers=headers, proxy=proxy, params=params if method == "get" else None,
            data=payload if isinstance(payload, str) else None,
            json=payload if isinstance(payload, dict) or isinstance(payload, list) else None
        )

        return self.handle_sync_response(response, parse_json, book_name)

    def handle_sync_response(self, response: CurlResponse, parse_json: bool, book_name: str) -> dict | None:
        """Handle a curl_cffi (non-async) response."""
        if response.status_code in self.valid_status_codes:
            try:
                return response.json() if parse_json else response.text
            except json.JSONDecodeError:
                self._capture_error(book_name, "Failed to parse JSON")
        else:
            self.check_403(response.status_code, book_name)
            # self._capture_error(book_name, f"Invalid status code {response.status_code}")

        return None

    async def handle_async_response(self, response: ClientResponse, parse_json: bool, book_name: str) -> dict | None:
        """Handle aiohttp async response."""
        # if response.status not in self.valid_status_codes:
        #     print(f"\n******* Failed {book_name} | Text: {await response.text()} *************\n", response.status)

        if response.status in self.valid_status_codes:
            try:
                if parse_json:
                    text = await response.text()
                    print(text)
                    return json.loads(text)

                return await response.json()

            except json.JSONDecodeError:
                self._capture_error(book_name, "Failed to parse JSON")
            except aiohttp.client_exceptions.ContentTypeError:
                return await response.json(content_type=None)
        else:
            self.check_403(response.status, book_name)
            # self._capture_error(book_name, f"Invalid status code {response.status}")

        return None


    def _capture_error(self, book_name: str, reason: str):
        pass
        # with sentry_sdk.new_scope() as scope:
        #     scope.set_tag("book_name", book_name)
        #     scope.set_tag("reason", reason)
        #     sentry_sdk.capture_message(f"Error for {book_name}: {reason}", level="error")
