import aiohttp
import os
from dotenv import load_dotenv
from Settings.book_base import SportbookRequestType
from Settings.proxy_manger import ProxyManager
from Settings.sgp_book_base import SGPBookBase
import asyncio

class Kambi_SGP(SGPBookBase):
    def __init__(self, links, **kwargs):
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="kambi_sgp.log", sportsbook_name="kambi", links=links, **kwargs)
        load_dotenv()

    @SGPBookBase.require_link_data
    async def run_book(self):
        bet_id_list = ",".join([bet_id.get("bet_id") for bet_id in self.link_data])
        event_id = next(iter({item["event_id"] for item in self.link_data}))

        async with aiohttp.ClientSession() as session:
            # Geo-Location issues, must use this proxy.
            PROXY = os.getenv("KAMBI_PROXY")
            proxy_manager = ProxyManager(self.api_caller, proxies=[PROXY])

            raw_api_data = await proxy_manager.proxy_controller(
                session=session,
                url=self.book_data.url.get("main_url").format(event_id=event_id, bet_ids=bet_id_list),
                method=self.book_data.method,
            )

            api_data = self.check_api_response(sportsbook="kambi", results=raw_api_data)
            if not api_data:
                return

            api_data.pop("success")

            if api_data and isinstance(api_data, dict):
                odds = api_data.get("selectedOdds")

                if odds:
                    return {
                        "decimal": float(odds.get("decimal")),
                        "american": float(odds.get("american")),
                    }

            return None

if __name__ == "__main__":
    links = [
        "https://{state}.betrivers.com/?page=sportsbook#event/1024870665?coupon=single|3864636183|"
        "https://{state}.betrivers.com/?page=sportsbook#event/1024870665?coupon=single|3870944295|",
    ]

    kambi = Kambi_SGP(links)
    data = asyncio.run(kambi.run_book())
    print(data)