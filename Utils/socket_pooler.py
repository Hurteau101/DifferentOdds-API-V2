# import asyncio
# import json
# from curl_cffi import requests as cf_requests
#
# class SocketPooler:
#     def __init__(self, url: str, headers: dict, size=10):
#         self.url = url
#
#         if not self.url.startswith("ws://") and not self.url.startswith("wss://"):
#             raise ValueError("URL must start with ws:// or wss://")
#
#         self.headers = headers or {}
#         self.size = size
#         self.session = None
#         self._lock = None
#         self._pool = None
#
#     @property
#     def lock(self):
#         if self._lock is None:
#             self._lock = asyncio.Lock()
#         return self._lock
#
#     @property
#     def pool(self):
#         if self._pool is None:
#             self._pool = asyncio.Queue()
#         return self._pool
#
#     async def send(self, payload: dict):
#         if self._lock is not None:
#             try:
#                 loop = asyncio.get_running_loop()
#                 if self._lock._loop is not loop:
#                     self._lock = None
#                     self._pool = None
#                     self.session = None
#             except RuntimeError:
#                 pass
#
#         async with self.lock:
#             if self.session is None:
#                 self.session = cf_requests.AsyncSession(impersonate="safari15_5")
#                 self._pool = asyncio.Queue()
#                 for _ in range(self.size):
#                     ws = await self.session.ws_connect(
#                         self.url,
#                         headers=self.headers
#                     )
#
#                     # Preload the pool with WebSocket connections
#                     await self.pool.put(ws)
#
#         ws = await self.pool.get()
#         try:
#             await ws.send_json(payload)
#             received_msg = await ws.recv()
#             if isinstance(received_msg, tuple):
#                 received_msg, _ = received_msg
#
#             result = json.loads(received_msg)
#
#             await self.pool.put(ws)  # Return the WebSocket to the pool
#             return result
#         except Exception as e:
#             print(e)
#             self._pool = None
#             self.session = None  # Reset the session on error to trigger reconnection
#             return {}
#

# import json
# from curl_cffi import requests as cf_requests
#
# class SocketHelper:
#     def __init__(self, url: str, headers: dict):
#         self.url = url
#
#         if not self.url.startswith("ws://") and not self.url.startswith("wss://"):
#             raise ValueError("URL must start with ws:// or wss://")
#
#         self.headers = headers or {}
#
#     async def send(self, payload: dict):
#         try:
#             async with cf_requests.AsyncSession() as session:
#                 ws = await session.ws_connect(self.url, headers=self.headers)
#                 await ws.send_json(payload)
#                 received_msg = await ws.recv()
#                 if isinstance(received_msg, tuple):
#                     received_msg, _ = received_msg
#                 return json.loads(received_msg)
#         except Exception as e:
#             print(e)
#             return {}
import json
import os
from itertools import cycle
from curl_cffi import requests as cf_requests
from dotenv import load_dotenv

load_dotenv()

class SocketHelper:
    def __init__(self, url: str, headers: dict):

        self.url = url
        if not self.url.startswith("ws://") and not self.url.startswith("wss://"):
            raise ValueError("URL must start with ws:// or wss://")

        self.headers = headers or {}

        self.proxies = os.getenv("RESIDENTIAL_PROXIES", "").split(",") if os.getenv("RESIDENTIAL_PROXIES") else []
        self._proxy_cycle = cycle(self.proxies) if self.proxies else None


    def _next_proxy(self) -> str | None:
        if not self._proxy_cycle:
            return None
        proxy = next(self._proxy_cycle)
        ip, port, username, password = proxy.split(":")
        return f"http://{username}:{password}@{ip}:{port}"


    async def send(self, payload: dict):
        # attempts = len(self.proxies) if self.proxies else 1

        #http://yxzikPTfJzmuIO2:3yMP0A9WCACBAc3@204.252.85.110:48067
        proxy = os.getenv("FLOPPYDATA_PROXY_URL")
        if not proxy:
            raise ValueError("FLOPPYDATA_PROXY_URL environment variable is not set.")

        for _ in range(10):
            # proxy = self._next_proxy()

            try:
                async with cf_requests.AsyncSession(impersonate="safari15_5") as session:
                    ws = await session.ws_connect(self.url, headers=self.headers, proxy=proxy)
                    await ws.send_json(payload)
                    received_msg = await ws.recv()
                    if isinstance(received_msg, tuple):
                        received_msg, _ = received_msg
                    return json.loads(received_msg)
            except Exception as e:
                # print(f"Proxy failed ({proxy}): {e} — trying next")
                continue

        print("All proxies failed [Websocket]")
        return {}