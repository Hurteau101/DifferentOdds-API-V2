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

    def _header_conflict_check(self, additional_headers: dict, default_headers: bool):
        if default_headers and additional_headers:
            conflicting = [key for key in additional_headers if key.lower() in self.FINGERPRINT_HEADERS]

            if conflicting:
                raise ValueError(
                    f"Headers '{','.join(conflicting)}' conflict with impersonate's fingerprint-consistent defaults "
                    f"and would cause detection mismatches. Remove them or pass default_headers=False."
                )

    async def _caller(self, session: CurlAsyncSession, url: str, valid_codes: list | None, method: str, parse_text:bool,
                      **kwargs) -> CallResult:
        if not valid_codes:
            valid_codes = [200]

        try:
            request = await session.request(method=method, url=url, **kwargs)

            if request.status_code not in valid_codes:
                return CallResult(ok=False, data={}, status_code=request.status_code, text=request.text)

            data = json.loads(request.text) if parse_text else request.json()

            return CallResult(ok=True, data=data, status_code=request.status_code, text=request.text)

        except Exception as e:

            return CallResult(ok=False, data={}, status_code=None, text=repr(e))


    async def api_caller(self, url: str, session: CurlAsyncSession|None = None, valid_codes:list|None = None, method: str = "GET",
                         use_proxy:bool = False, proxy_list: list|None = None, proxy_impersonate: str="chrome", parse_text:bool = False, **kwargs):
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
        self._header_conflict_check(additional_headers=kwargs.get("headers"), default_headers=kwargs.get("default_headers", True))

        if not use_proxy:
            if not session:
                raise ValueError("session is required if use_proxy is False")

            result = await self._caller(session=session, url=url, valid_codes=valid_codes, method=method, parse_text=parse_text, **kwargs)

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
                    parse_text=parse_text,
                    **kwargs
                )

            if result.ok:
                return result.data

            errors.append({
                "Proxy": proxy,
                "Status": result.status_code,
                "Body": result.text,
            })

        logger.error(f"All proxies failed | Errors: {json.dumps(errors, indent=2)})")

        return {}





