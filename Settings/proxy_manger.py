import inspect
import os
from itertools import cycle

from aiohttp import ClientHttpProxyError
from dotenv import load_dotenv
from tls_client.exceptions import TLSClientExeption

from Settings.book_base import BookBase
from Settings.logger import FileLogger

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

class ProxyManager:
    def __init__(self, api_caller_func):
        load_dotenv(dotenv_path=env_path)
        self.proxy_list = os.getenv("PROXIES").split(",") if os.getenv("PROXIES") else ""
        self.proxy_amount = len(self.proxy_list)
        self.proxy_pool = cycle(self.proxy_list)

        self.api_caller = api_caller_func

        self.file_logger = FileLogger()


        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(current_dir, "Proxy.log")

        self.file_logger.set_log_file(log_path)
        caller_file_full = inspect.stack()[1].filename


        self.caller_file_name = os.path.basename(caller_file_full)  # File name of the caller

    async def proxy_controller(self, url, method, headers=None, session=None, client_identifier=None, sync_type="async"):
        if sync_type == "async":
            return await self.proxy_caller_async(session, url, method, headers)
        else:
            return await self.proxy_caller_spoof(url, method, headers, client_identifier)

    def _cycle_proxies(self):
        proxy = next(self.proxy_pool)

        if not proxy:
            self.file_logger.log(
                message=f"{self.caller_file_name} - No proxy found",
                level="INFO"
            )
            return None

        proxy_parts = proxy.split(":")
        ip, port, username, password = proxy_parts

        return f"http://{username}:{password}@{ip}:{port}"


    async def proxy_caller_async(self, session, url, method, headers):
        for i in range(self.proxy_amount):
            proxy = self._cycle_proxies()
            if proxy:
                try:
                    api_data = await self.api_caller(
                        session=session,
                        url=url,
                        method=method,
                        proxy=proxy,
                        headers=headers
                    )

                    if api_data:
                        return api_data

                    continue
                except ClientHttpProxyError as e:
                    self.file_logger.log(
                        message=f"Proxies Issue",
                        file=f"{self.caller_file_name}",
                        proxy=proxy,
                        proxy_message=e,
                        level="INFO"
                    )
                    continue

    async def proxy_caller_spoof(self, url, method, headers, client_identifier="chrome_114"):
        for i in range(self.proxy_amount):
            proxy = self._cycle_proxies()
            if proxy:
                try:
                    api_data = await self.api_caller(
                        url=url,
                        method=method,
                        headers=headers,
                        client_identifier=client_identifier,
                        proxy=proxy
                    )

                    if api_data:
                        return api_data

                    continue
                except TLSClientExeption as e:
                    self.file_logger.log(
                        message=f"Proxies Issue",
                        file=f"{self.caller_file_name}",
                        proxy=proxy,
                        proxy_message=e,
                        level="INFO"
                    )
                    continue

if __name__ == "__main__":
    proxy = ProxyManager()
    print(proxy.proxy_amount)