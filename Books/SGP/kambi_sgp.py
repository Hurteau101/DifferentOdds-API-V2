import asyncio
import aiohttp
from dotenv import load_dotenv
import os
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
from Utils.proxy_manger import ProxyManager

class KambiSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="kambi", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self):
        bet_id_list = ",".join([bet_id.get("bet_id") for bet_id in self.link_data])
        event_id = next(iter({item["event_id"] for item in self.link_data}))

        async with aiohttp.ClientSession() as session:
            # Geo-Location issues, must use this proxy.
            proxy = os.getenv("KAMBI_PROXY")
            proxy_manger = ProxyManager(self.api_caller, proxies=[proxy])

            api_data = await proxy_manger.proxy_caller(
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
