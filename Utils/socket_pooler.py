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

import json
from curl_cffi import requests as cf_requests

class SocketHelper:
    def __init__(self, url: str, headers: dict):
        self.url = url

        if not self.url.startswith("ws://") and not self.url.startswith("wss://"):
            raise ValueError("URL must start with ws:// or wss://")

        self.headers = headers or {}

    async def send(self, payload: dict):
        try:
            async with cf_requests.AsyncSession() as session:
                ws = await session.ws_connect(self.url, headers=self.headers)
                await ws.send_json(payload)
                received_msg = await ws.recv()
                if isinstance(received_msg, tuple):
                    received_msg, _ = received_msg
                return json.loads(received_msg)
        except Exception as e:
            print(e)
            return {}