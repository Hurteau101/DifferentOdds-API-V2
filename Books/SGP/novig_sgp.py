import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType


class NovigSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="novig", sgp_data=sgp_data, **kwargs)

    def _extract_odds(self, api_data: list) -> float | None:
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

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("main_url"),
            method="POST",
            payload=payload
        )


        if not api_data:
            return None


        if api_data:
            american_odds = self._extract_odds(api_data)
            return NovigSGP.return_odds(american_odds=american_odds, decimal_odds=None) if american_odds else None


        return None