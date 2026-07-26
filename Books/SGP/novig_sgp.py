import asyncio
import os

import aiohttp
from dotenv import load_dotenv

from Books.Bases.sgp_book_base import SGPBookBase
from Utils.proxy_manger import ProxyManager
from Utils.request_caller import SportbookRequestType

load_dotenv()

class NovigSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="novig", sgp_data=sgp_data, **kwargs)

    def _extract_odds(self, api_data: list, is_sgp: bool) -> float | None:
        if is_sgp:
            check_sgp = set(
                leg.get("outcome", {}).get("market", {}).get("event", {}).get("game", {}).get("id")
                for odds in api_data
                for leg in odds.get("legs", [])
                if leg.get("outcome", {}).get("market", {}).get("event", {}).get("game", {}).get("id")
            )

            # Ensure that it's a SGP
            if len(check_sgp) > 1:
                return None

        probability = "".join([
            str(odds["price"])
            for odds in api_data
        ])

        return NovigSGP.convert_probability_to_american_odds(probability)


    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):

        ids = [{"id": link.get("event_id")} for link in self.link_data]


        payload = {
            "boostId": None,
            "outcomes": ids
        }

        is_sgp = self.sgp_data.get("is_sgp", True)

        proxy_1 = os.getenv("RESIDENTIAL_PROXIES")
        proxy_2 = os.getenv("PROXIES")
        proxies = [
            prx
            for proxy in [proxy_1, proxy_2] if proxy
            for prx in proxy.split(",")
        ]

        proxy_manager = ProxyManager(proxies=proxies, api_caller_func=self.api_caller)

        if not is_sgp:
            api_data = await proxy_manager.rotating_proxy_caller(
                book_name=self.book_data.name,
                session=session,
                headers=self.book_data.headers,
                url=self.book_data.url.get("main_url"),
                method="POST",
                payload=payload
            )


        # api_data = await self.api_caller(
        #     book_name=self.book_data.name,
        #     headers=self.book_data.headers,
        #     session=session,
        #     url=self.book_data.url.get("main_url"),
        #     method="POST",
        #     payload=payload
        # )

        # api_data = await proxy_manager.proxy_caller(
        #     book_name=self.book_data.name,
        #     session=session,
        #     headers=self.book_data.headers,
        #     url=self.book_data.url.get("main_url"),
        #     method="POST",
        #     payload=payload
        # )



        if not api_data:
            return None

        if api_data:
            american_odds = self._extract_odds(api_data, is_sgp=is_sgp)
            return NovigSGP.return_odds(american_odds=american_odds, decimal_odds=None) if american_odds else None


        return None


if __name__ == "__main__":
    async def main():
        async with aiohttp.ClientSession() as session:
            sgp_data = {
                "book_name": "novig",
                "links": ["https://novig.com/events/019f9c03-665e-7380-96b8-5cf45707f310/null",
                          "https://novig.com/events/019f9ec8-4fa3-71a0-a76b-48407921ef9e/null"],
                "is_sgp": False
            }
            novig_sgp = NovigSGP(sgp_data=sgp_data)
            results = await novig_sgp.run_book(session=session)
            print(results)

    asyncio.run(main())