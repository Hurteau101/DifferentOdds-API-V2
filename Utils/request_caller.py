import json
from curl_cffi import AsyncSession as CurlAsyncSession
import logging
from random import shuffle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class APICaller:
    def __init__(self):
        self.default_codes = [200]

    async def _caller(self, session: CurlAsyncSession, url: str, valid_codes:list|None, method: str, **kwargs):
        request = await session.request(method=method, url=url, **kwargs)
        if not valid_codes:
            valid_codes = self.default_codes

        if request.status_code in valid_codes:
            try:
                return request.json()
            except json.decoder.JSONDecodeError:
                logger.error(f"Failed to parse JSON: {request.text}")
                return {}

        logger.warning(f"Request failed with status code: {request.status_code}")
        return {}

    async def api_caller(self, session: CurlAsyncSession, url: str, valid_codes:list|None = None, method: str = "GET",
                         use_proxy:bool = False, proxy_list: list = None, **kwargs):
        """
        Helper function to make API calls.
        :param session: The session to use
        :param url: The URL to be called.
        :param valid_codes: List of valid status codes. If response isn't in valid_codes, will return {}. Default: 200
        :param method: The HTTP method to use. Default: GET
        :param use_proxy: Whether to use proxy or not. Default: False
        :param proxy_list: List of connection strings. Default: None
        :param kwargs: Additional parameters to be passed to the API call.
        :return: The response from the API OR an empty dict.
        """
        if use_proxy and not proxy_list:
            raise ValueError("Proxy list is empty. Please provide a list of connection strings")

        if not use_proxy:
            return await self._caller(session=session, url=url, valid_codes=valid_codes, method=method, **kwargs)

        # Shuffle to avoid the same order of proxies.
        shuffle(proxy_list)
        print("Hitting Proxies")

        for conn in range(0, len(proxy_list)):
            kwargs["proxy"] = {"http": conn}

            response = await self._caller(
                session=session,
                url=url,
                valid_codes=valid_codes,
                method=method,
                **kwargs
            )

            if response:
                return response

        logger.info("Failed all proxies")

        return {}





