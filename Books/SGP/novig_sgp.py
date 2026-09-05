import asyncio
from dotenv import load_dotenv
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession
from Utils.helpers import convert_probability_to_american_odds

load_dotenv()

class NovigSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="novig", sgp_data=sgp_data, **kwargs)

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

        return convert_probability_to_american_odds(probability)


    @SGPBookBase.ensure_link_data
    async def run_book(self, session):

        ids = [{"id": link.get("event_id")} for link in self.link_data]

        payload = {
            "boostId": None,
            "outcomes": ids
        }

        is_sgp = self.sgp_data.get("is_sgp", True)

        api_data = await self.api_caller(
            use_proxy=True,
            headers=self.book_data.headers,
            url=self.book_data.url.get("main_url"),
            method="POST",
            json=payload,
            valid_codes=[201],
            proxy_abort_text=['Cannot price parlay']
        )

        if not api_data:
            return None

        if api_data:
            american_odds = self._extract_odds(api_data, is_sgp=is_sgp)
            return NovigSGP.return_odds(american_odds=american_odds, decimal_odds=None) if american_odds else None


        return None


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                "book_name": "novig",
                "links": [
                    "https://novig.com/events/01a06dee-ed49-7c91-be67-8c163c405e29/null?referralCode=null",
                    "https://novig.com/events/01a06dee-ed49-7c91-be67-8ba5f56f7c4f/null?referralCode=null"
                ],
                "is_sgp": True
            }
            novig_sgp = NovigSGP(sgp_data=sgp_data)
            results = await novig_sgp.run_book(session=session)
            print(results)

    asyncio.run(main())