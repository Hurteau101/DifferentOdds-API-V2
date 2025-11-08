import os
import aiohttp
from dotenv import load_dotenv
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Prophet_SGP(SGPBookBase):
    def __init__(self, links):
        load_dotenv()
        super().__init__(request_type=SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="prophet_sgp.log", sportsbook_name="prophetx", links=links)



    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            headers = self.book_data.headers
            headers.update({
                "X-Auth-Affiliate": os.getenv("PROPHET_AFFILIATE_KEY"),
            })

            links_list = [
                links_id.get("bet_id")
                for links_id in self.link_data
            ]

            api_data = await self.api_caller(
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
                self._api_call_log("prophet_sgp")
                return


            if len(api_data.get("offers")) <= 0:
                return None

            return {
                "decimal": None,
                "american": float(api_data.get("offers")[0].get("odds"))
            }




if __name__ == "__main__":
    import asyncio

    links = [
        "https://www.prophetx.co/?action=addtobetslip&lineID=a747def04602dfe255dfb63f3a049e59&partner_id=null&currency=cash",
        "https://www.prophetx.co/?action=addtobetslip&lineID=4559592eb00b547925a128137af3e3ca&partner_id=null&currency=cash"
    ]

    prophet_sgp = Prophet_SGP(links)
    data = asyncio.run(prophet_sgp.run_book())
    print(data)


