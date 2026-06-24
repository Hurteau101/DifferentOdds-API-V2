import asyncio
import json
import time

from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
from seleniumbase.undetected.cdp_driver import cdp_util

class DraftkingsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.SPOOF, category="SGP", book_name="draftkings", sgp_data=sgp_data, **kwargs)

    async def post_odds(self, payload: dict, retry=3):
        """POST via the persistent browser's session over CDP, with retries for refresh/restart timing."""
        for _ in range(retry):
            try:
                driver = await cdp_util.start_async(host="127.0.0.1", port=9222)
                page = driver.main_tab

                javascript_inject = """
                    (async () => {
                        const payload = %s;
                        try {
                            const response = await fetch("%s", {
                                method: "POST",
                                credentials: "include",
                                headers: {"Accept": "application/json", "Content-Type": "application/json"},
                                body: JSON.stringify(payload)
                            });
                            const text = await response.text();
                            return {status: "ok", body: text};
                        } catch (e) {
                            return {status: "error", body: e.toString()};
                        }
                    })()
                """ % (json.dumps(payload), self.book_data.url.get("main_url"))
                return await page.evaluate(javascript_inject, await_promise=True, return_by_value=True)
            except Exception as e:
                await asyncio.sleep(1)
                continue

        return None


    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        selections = [
            { "id": link.get("outcome_id") }
            for link in self.link_data
        ]

        length_of_bet = len(self.link_data)

        # api_data = await self.api_caller(
        #     book_name=self.book_data.name,
        #     session=session,
        #     url=self.book_data.url.get("main_url"),
        #     method="POST",
        #     headers=self.book_data.headers,
        #     payload={
        #         "oddsStyle": "american",
        #         "selections": selections
        #     },
        # )

        api_data = await self.post_odds(payload={
            "oddsStyle": "american",
            "selections": selections
        })

        if not api_data:
            return None

        if api_data and isinstance(api_data, dict):
            if not api_data.get("combinabilityRestrictions"):
                sgp_odds_list = api_data.get("bets", [])

                if isinstance(sgp_odds_list, list):
                    sgp_bet = next((bet for bet in sgp_odds_list if len(bet.get("selectionsMapped")) == length_of_bet), None)

                    if sgp_bet:
                        return DraftkingsSGP.return_odds(
                            american_odds=str(sgp_bet.get("displayOdds")).replace("−", "-"),
                            decimal_odds=None
                        )
        return None

if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome_android") as session:
            sgp_data = {'book_name': 'draftkings', 'links': ['https://sportsbook.draftkings.com/event/33742178?outcomes=0OU83722837O11950_1', 'https://sportsbook.draftkings.com/event/33742178?outcomes=0OU83681931O23450_1']}

            book = DraftkingsSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
