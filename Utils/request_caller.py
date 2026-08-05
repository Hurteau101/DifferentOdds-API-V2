import json
import os
from dataclasses import dataclass
from curl_cffi import AsyncSession as CurlAsyncSession
import logging
from random import shuffle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

@dataclass
class CallResult:
    ok: bool
    data: dict
    status_code: int | None
    text: str | None = None


class APICaller:
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


    async def api_caller(self, url: str, session: CurlAsyncSession|None = None, valid_codes:list|None = None, method: str = "GET",
                         use_proxy:bool = False, proxy_list: list|None = None, proxy_impersonate: str="chrome", **kwargs):
        """
        Helper function to make API calls using curl_cffi.
        :param url: The URL to be called.
        :param session: The session to use. Required if not using proxy. Default: None
        :param valid_codes: List of valid status codes. If the response isn't in valid_codes, it will return {}. Default: 200
        :param method: The HTTP method to use. Default: GET
        :param use_proxy: Whether to use proxy or not. Default: False
        :param proxy_list: List of connection strings. Proxy format USERNAME:PASSWORD@HOST:PORT Default: RESIDENTIAL_PROXIES environment variable
        :param proxy_impersonate: The browser to impersonate. Default: chrome
        :param kwargs: Additional parameters passed through to curl_cffi's session.request(). See the
            curl_cffi docs for all supported options (headers, params, json, data, auth, cookies, timeout,
            default_headers, allow_redirects, multipart, etc.): https://curl-cffi.readthedocs.io/en/latest/quick_start.html
        :return: The response from the API OR an empty dict.
        """

        if not use_proxy:
            if not session:
                raise ValueError("session is required if use_proxy is False")

            result = await self._caller(session=session, url=url, valid_codes=valid_codes, method=method, **kwargs)

            if not result.ok:
                logger.error(f"Request failed | Status: {result.status_code} | Body: {result.text}")

            return result.data

        if not proxy_list:
            # Use default proxy list if not provided.
            proxy_list = os.getenv("RESIDENTIAL_PROXIES", "").split(",") if os.getenv("RESIDENTIAL_PROXIES") else []
            if not proxy_list:
                raise ValueError("RESIDENTIAL_PROXIES environment variable is not set.")

        # Shuffle to avoid the same order of proxies.
        shuffled_proxies = list(proxy_list)
        shuffle(shuffled_proxies)

        errors = []

        for proxy in shuffled_proxies:
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





