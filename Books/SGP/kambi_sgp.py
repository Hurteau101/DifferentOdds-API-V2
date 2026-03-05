import asyncio
import aiohttp
from dotenv import load_dotenv
import os
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
from Utils.proxy_manger import ProxyManager
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_result

class KambiSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="kambi", retry_amount=5, sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=False)
    async def run_book(self):
        bet_id_list = ",".join([bet_id.get("bet_id") for bet_id in self.link_data])
        event_id = next(iter({item["event_id"] for item in self.link_data}))

        async with aiohttp.ClientSession() as session:
            # Geo-Location issues, must use this proxy.
            # proxy = os.getenv("KAMBI_PROXY")
            # proxy_manger = ProxyManager(self.api_caller, proxies=[proxy])

            # api_data = await proxy_manger.proxy_caller(
            #     book_name=self.book_data.name,
            #     session=session,
            #     url=self.book_data.url.get("main_url").format(event_id=event_id, bet_ids=bet_id_list),
            #     method=self.book_data.method,
            # )

            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url").format(event_id=event_id, bet_ids=bet_id_list),
                method=self.book_data.method,
            )

            if not api_data:
                return None

            if api_data and isinstance(api_data, dict):
                odds = api_data.get("selectedOdds")
                return KambiSGP.return_odds(american_odds=odds.get("american"), decimal_odds=odds.get("decimal")) if odds else None


if __name__ == "__main__":

    sgp_data = {'book_name': 'kambi', 'links': ['https://{state}.betrivers.com/?page=sportsbook#event/1024653530?coupon=single|4090179708|', 'https://{state}.betrivers.com/?page=sportsbook#event/1024653530?coupon=single|4090171422|']}

    book = KambiSGP(sgp_data=sgp_data)
    data = asyncio.run(book.run_book())
    print(data)

