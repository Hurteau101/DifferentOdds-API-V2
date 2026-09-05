import json
import os
from itertools import cycle
from random import shuffle
from curl_cffi import requests as cf_requests
from dotenv import load_dotenv
from Utils.request_caller import PredefinedProxy, check_proxy_format
from loguru import logger
import sys

load_dotenv()

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {file}:{line} {function} | {message}")


class SocketHelper:
    def __init__(self, url: str, headers: dict):
        self.url = url
        if not self.url.startswith("ws://") and not self.url.startswith("wss://"):
            raise ValueError("URL must start with ws:// or wss://")

        self.headers = headers or {}


    async def _send(self, session: cf_requests.AsyncSession, payload: dict, proxy: str | None = None) -> dict | None:
        try:
            ws = await session.ws_connect(self.url, headers=self.headers, proxy=proxy)
            await ws.send_json(payload)

            received_msg = await ws.recv()

            if isinstance(received_msg, tuple):
                received_msg, _ = received_msg

            return json.loads(received_msg)
        except Exception as e:
            logger.opt(depth=1).error(f"Connection failed | Proxy: {proxy} | Error: {e}")
            return None


    async def send(self, payload, proxy_list: list | None = None, use_proxy: bool = True):
        if not use_proxy:
            return await self._send(cf_requests.AsyncSession(impersonate="safari15_5"), payload)

        if not proxy_list:
            # Use default proxy list if not provided.
            proxy_list = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value

            if not proxy_list:
                raise ValueError("RESIDENTIAL_PROXIES environment variable is not set.")

        shuffled_proxies = list(proxy_list)
        valid_proxies = [proxy for proxy in shuffled_proxies if check_proxy_format(proxy)]

        if not valid_proxies:
            raise ValueError(f"No valid proxy formats in proxy list. Format should be USERNAME:PASSWORD@HOST:PORT")

        shuffle(valid_proxies)

        for proxy in valid_proxies:
            async with cf_requests.AsyncSession(impersonate="safari15_5") as session:
                result = await self._send(session, payload, proxy)
                if result:
                    return result