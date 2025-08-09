import asyncio
from Settings.proxy_manger import ProxyManager
import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase


class Prizepicks(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="prizepicks")



    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            proxy_manger = ProxyManager(self.api_caller)
            data = await proxy_manger.proxy_controller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            print(data)

if __name__ == "__main__":
    prizepicks = Prizepicks()
    asyncio.run(prizepicks.run_book())
