import asyncio
from dotenv import load_dotenv
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession

class KambiSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="kambi", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session):
        bet_id_list = ",".join([bet_id.get("bet_id") for bet_id in self.link_data])
        event_id = next(iter({item["event_id"] for item in self.link_data}))

        api_data = await self.api_caller(
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
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {'book_name': 'kambi', 'links': [
                "https://{state}.betrivers.com/?page=sportsbook#event/1024787556?coupon=single|4319709181|",
                "https://{state}.betrivers.com/?page=sportsbook#event/1024787556?coupon=single|4319718284|"
                        ]}
            book = KambiSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
