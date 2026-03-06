import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType


class DraftkingsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="draftkings", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            selections = [
                { "id": link.get("outcome_id") }
                for link in self.link_data
            ]

            length_of_bet = len(self.link_data)

            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method="POST",
                headers=self.book_data.headers,
                payload={
                    "oddsStyle": "american",
                    "selections": selections
                },
            )

            if not api_data:
                return None

            if api_data and isinstance(api_data, dict):
                if not api_data.get("combinabilityRestrictions"):
                    sgp_odds_list = api_data.get("bets", [])

                    if isinstance(sgp_odds_list, list):
                        sgp_bet = next((bet for bet in sgp_odds_list if len(bet.get("selectionsMapped")) == length_of_bet), None)

                        if sgp_bet:
                            return DraftkingsSGP.return_odds(
                                american_odds=str(sgp_bet.get("displayOdds")).replace("−", "-"),
                                decimal_odds=None
                            )
            return None

if __name__ == "__main__":
    sgp_data = {'book_name': 'draftkings', 'links': ['https://sportsbook.draftkings.com/event/33742178?outcomes=0OU83722837O11950_1', 'https://sportsbook.draftkings.com/event/33742178?outcomes=0OU83681931O23450_1']}

    book = DraftkingsSGP(sgp_data=sgp_data)
    data = asyncio.run(book.run_book())
    print(data)
