import asyncio
import os
from Books.Bases.sgp_book_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession


class ProphetxSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="prophetx", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
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
                sgp_data = {'book_name': 'prophetx', 'links': ['https://www.prophetx.co/?action=addtobetslip&lineID=881bfbeec4d3c089bcd0ee9a32cd5d53&partner_id=null&currency=cash', 'https://www.prophetx.co/?action=addtobetslip&lineID=71152995a5239b78e694b87254c1b8ef&partner_id=null&currency=cash']}

                book = ProphetxSGP(sgp_data)
                data = await book.run_book(session=session)
                print(data)


        asyncio.run(main())

    # sgp_data = {'book_name': 'prophetx', 'links': ['https://www.prophetx.co/?action=addtobetslip&lineID=881bfbeec4d3c089bcd0ee9a32cd5d53&partner_id=null&currency=cash', 'https://www.prophetx.co/?action=addtobetslip&lineID=71152995a5239b78e694b87254c1b8ef&partner_id=null&currency=cash']}
    #
    # book = ProphetxSGP(sgp_data=sgp_data)
    # data = asyncio.run(book.run_book())
    # print(data)
