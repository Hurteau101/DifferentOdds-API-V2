import asyncio
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.sgp_base import SGPBookBase

class DraftkingsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="draftkings", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session) -> dict | None:
        selections = [
            { "id": link.get("outcome_id") }
            for link in self.link_data
        ]

        length_of_bet = len(self.link_data)

        api_data = await self.api_caller(
            session=session,
            default_headers=False,
            url=self.book_data.url.get("main_url"),
            method="POST",
            headers=self.book_data.headers,
            json={
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
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {
                'book_name': 'draftkings',
                'links': [
                    "https://sportsbook.draftkings.com/event/34599443?outcomes=0QA365526010%232267250591_13L84240Q1-1570309299Q20",
                    "https://sportsbook.draftkings.com/event/34599443?outcomes=0QA365525887%232267250594_13L84240Q1-811205453Q20"
                ]
            }

            book = DraftkingsSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())