import asyncio
import os
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession


class ProphetxSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="prophet x", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session):
        headers = self.book_data.headers
        headers.update({
            "X-Auth-Affiliate": os.getenv("PROPHET_AFFILIATE_KEY"),
        })

        links_list = [
            links_id.get("line_id")
            for links_id in self.link_data
        ]

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("main_url"),
            method=self.book_data.method,
            headers=self.book_data.headers,
            json={
                "stake": 1.0,
                "line_ids": links_list
            }
        )

        if not api_data:
            return None

        if len(api_data.get("offers")) <= 0:
            return None

        return ProphetxSGP.return_odds(
            american_odds=api_data.get("offers")[0].get("odds"),
            decimal_odds=None
        )

if __name__ == "__main__":
    if __name__ == "__main__":
        async def main():
            async with CurlAsyncSession(impersonate="chrome") as session:
                sgp_data = {'book_name': 'prophetx', 'links': [
                    "https://www.prophetx.co/?action=addtobetslip&lineID=30e3d3312eabbe5b8f2bb5d51cb76127&partner_id=null",
                    "https://www.prophetx.co/?action=addtobetslip&lineID=28a16a07b8bddf9f11a14525c6e96b57&partner_id=null"
                ]}

                book = ProphetxSGP(sgp_data)
                data = await book.run_book(session=session)
                print(data)


        asyncio.run(main())
