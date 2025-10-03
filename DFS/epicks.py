import aiohttp
import asyncio
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase


class Epicks(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="epicks")

    def _extract_leagues(self, league_data):
        return set(
            league
            for league, additional_info in league_data.items()\
            if additional_info.get("status") == "ACTIVE"
        )

    async def _get_league_data(self, league, session):

        # Recursive function to handle pagination
        async def _pagination_runner(cursor_payload=None):
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url").format(league=league),
                method="POST",
                payload=cursor_payload if cursor_payload else {}
            )

            if not api_data:
                return None

            if api_data.get("next_cursor"):
                await _pagination_runner(
                    cursor_payload={
                        "cursor": api_data.get("next_cursor")
                    }
                )

        await _pagination_runner()




    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_url"),
                method=self.book_data.method,
            )

            if not league_data:
                self.file_logger.log(
                    message="Couldn't map leagues for Epicks",
                )
                return None

            leagues = self._extract_leagues(league_data)

            leagues = ["nfl"]

            tasks = [
                self._get_league_data(league, session)
                for league in leagues
            ]

            await asyncio.gather(*tasks)

if __name__ == "__main__":
    epicks = Epicks()
    asyncio.run(epicks.run_book())