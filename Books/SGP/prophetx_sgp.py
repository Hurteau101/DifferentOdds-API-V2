import asyncio
import os
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType

class ProphetxSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="prophetx", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            headers = self.book_data.headers
            headers.update({
                "X-Auth-Affiliate": os.getenv("PROPHET_AFFILIATE_KEY"),
            })

            links_list = [
                links_id.get("line_id")
                for links_id in self.link_data
            ]

            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
                payload={
                    "stake": 1.0,
                    "line_ids": links_list
                }
            )

            if not api_data:
                return

            if len(api_data.get("offers")) <= 0:
                return None

            return ProphetxSGP.return_odds(
                american_odds=api_data.get("offers")[0].get("odds"),
                decimal_odds=None
            )

