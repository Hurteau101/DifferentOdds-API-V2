import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase


class Betr(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="betr")


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                payload={
                    "operationName": "AllLeaguesUpcomingEvents",
                    "query": """query AllLeaguesUpcomingEvents {
                              getUpcomingEventsV2 {
                                id
                                league
                              }
                            }""",
                }
            )

            print(api_data)


if __name__ == "__main__":
    betr = Betr()
    import asyncio
    asyncio.run(betr.run_book())