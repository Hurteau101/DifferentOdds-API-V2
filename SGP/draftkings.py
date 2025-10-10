import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Draftkings_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(request_type=SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="draftkings_sgp.log", sportsbook_name="draftkings", links=links)


    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method="POST",
                headers=self.book_data.headers,
                payload={
                    "oddsStyle": "american",
                    "selections": [
                        {
                            "id": link.get("bet_id"),
                        }
                        for link in self.link_data
                    ],
                },
            )

            if not api_data:
                self._api_call_log("draftkings_spg")
                return

            if api_data and isinstance(api_data, dict):
                if not api_data.get("combinabilityRestrictions"):
                    sgp_odds_list = api_data.get("bets", [])
                    if isinstance(sgp_odds_list, list):
                        sgp_bet = next((bet for bet in sgp_odds_list if bet.get("type") == "YourBet"), None)
                        if sgp_bet:
                            return {
                                "decimal": None,
                                "american": float(str(sgp_bet.get("displayOdds")).replace("−", "-"))
                            }

            return None


if __name__ == "__main__":
    import asyncio

    links = [
        "https://sportsbook.draftkings.com/event/32789579?outcomes=0OU81309624U750_3",
        "https://sportsbook.draftkings.com/event/32789579?outcomes=0ML81309624_1"
    ]

    draftkings_sgp = Draftkings_SGP(links)
    data = asyncio.run(draftkings_sgp.run_book())
    print(data)