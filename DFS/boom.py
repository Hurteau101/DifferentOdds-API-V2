import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase

class Boom(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="boom")

    ###

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            print(api_data)




if __name__ == "__main__":
    import asyncio
    boom = Boom()

    data = asyncio.run(boom.run_book())