import os
import re
from dataclasses import dataclass
from curl_cffi import AsyncSession as CurlAsyncSession
import logging
from random import shuffle
import inspect
from enum import Enum
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()

@dataclass
class CallResult:
    ok: bool
    data: dict
    status_code: int | None
    text: str | None = None

class PredefinedProxy(Enum):
    PROXY_CHEAP_RESIDENTIAL_PROXIES = [proxy for proxy in os.getenv("PROXY_CHEAP_RESIDENTIAL_PROXIES", "").split(",") if proxy]

class APICaller:
    FINGERPRINT_HEADERS = [
        "user-agent",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "sec-fetch-user",
        "accept",
        "accept-language",
        "accept-encoding",
        "upgrade-insecure-requests",
        "priority",
    ]


    def _check_proxy_format(self, proxy: str):
        """Ensures that the proxy format is USERNAME:PASSWORD@HOST:PORT"""
        return bool(re.fullmatch(r'\S+:\S+@[\d.]+:\d+', proxy))

    def _header_conflict_check(self, additional_headers: dict, default_headers: bool, default_headers_override: list | None):
        if default_headers and additional_headers:

            default_headers_override = [key.lower() for key in default_headers_override] if default_headers_override else []

            conflicting = [
              key
              for key in additional_headers
              if key.lower() in self.FINGERPRINT_HEADERS and key.lower() not in default_headers_override
            ]

            if conflicting:
                raise ValueError(
                    f"Headers '{','.join(conflicting)}' conflict with impersonate's fingerprint-consistent defaults "
                    f"and would cause detection mismatches. Remove them or pass default_headers=False."
                )

    async def _caller(self, session: CurlAsyncSession, url: str, valid_codes: list | None, method: str,
                      **kwargs) -> CallResult:
        if not valid_codes:
            valid_codes = [200]

        try:
            request = await session.request(method=method, url=url, **kwargs)
            if request.status_code not in valid_codes:
                return CallResult(ok=False, data={}, status_code=request.status_code, text=request.text)

            return CallResult(ok=True, data=request.json(), status_code=request.status_code, text=request.text)

        except Exception as e:
            return CallResult(ok=False, data={}, status_code=None, text=repr(e))

    def _caller_information(self):
        """Get information about the caller."""
        _stack = inspect.stack()[1]
        return f"{_stack[0].f_locals['self'].__class__.__name__}.{_stack[3]}"


    async def api_caller(self, url: str, session: CurlAsyncSession|None = None, valid_codes:list|None = None, method: str = "GET",
                         use_proxy:bool = False, proxy_list: list[str]|None = None, proxy_impersonate: str="chrome",
                         default_header_override: list | None = None, **kwargs):
        """
        Helper function to make API calls using curl_cffi.
        :param url: The URL to be called.
        :param session: The session to use. Required if not using proxy. Default: None
        :param valid_codes: List of valid status codes. If the response isn't in valid_codes, it will return {}. Default: 200
        :param method: The HTTP method to use. Default: GET
        :param use_proxy: Whether to use proxy or not. Default: False
        :param proxy_list: List of connection strings. Proxy format USERNAME:PASSWORD@HOST:PORT Default: RESIDENTIAL_PROXIES environment variable
        :param proxy_impersonate: The browser to impersonate. Default: chrome
        :param default_header_override: List of header names to override in the default headers. Default: None
        :param kwargs:
            Additional parameters passed through to curl_cffi's session.request(). See the
            curl_cffi docs for all supported options (headers, params, json, data, auth, cookies, timeout,
            default_headers, allow_redirects, multipart, etc.): https://curl-cffi.readthedocs.io/en/latest/quick_start.html
            Additionally handled by this function:

            - "default_headers_override``: list of header names to override in the default headers.

        :return: The response from the API OR an empty dict.
        """

        self._header_conflict_check(
            additional_headers=kwargs.get("headers"),
            default_headers=kwargs.get("default_headers", True),
            default_headers_override=default_header_override
        )

        if not use_proxy:
            if not session:
                raise ValueError("session is required if use_proxy is False")

            result = await self._caller(session=session, url=url, valid_codes=valid_codes, method=method, **kwargs)

            if not result.ok:
                logger.error(f"[{self._caller_information()}] Request failed | Status: {result.status_code} | Body: {result.text}")

            return result.data

        if not proxy_list:
            # Use default proxy list if not provided.
            proxy_list = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value

            if not proxy_list:
                raise ValueError("RESIDENTIAL_PROXIES environment variable is not set.")

        # Shuffle to avoid the same order of proxies.
        shuffled_proxies = list(proxy_list)
        valid_proxies = [proxy for proxy in shuffled_proxies if self._check_proxy_format(proxy)]

        if not valid_proxies:
            raise ValueError(f"No valid proxy formats in proxy list. Format should be USERNAME:PASSWORD@HOST:PORT")

        shuffle(valid_proxies)

        errors = []

        for proxy in valid_proxies:
            # Create a new session for each proxy.
            async with CurlAsyncSession(impersonate=proxy_impersonate) as proxy_session:
                result = await self._caller(
                    session=proxy_session,
                    url=url,
                    valid_codes=valid_codes,
                    method=method,
                    proxy=proxy,
                    **kwargs
                )

            if result.ok:
                return result.data

            errors.append(f"Proxy: {proxy} | Status: {result.status_code} | Body: {result.text}")

        logger.error(f"All proxies failed | Errors: {errors}")

        return {}





