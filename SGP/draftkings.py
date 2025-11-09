import aiohttp
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Draftkings_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(request_type=SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="draftkings_sgp.log", sportsbook_name="draftkings", links=links)

    def format_selections(self):
        selections = []

        for link in self.link_data:
            if "%" in link.get("bet_id"):
                split_link = link.get("bet_id").split("%")
                if len(split_link) != 2:
                    continue

                first_half = split_link[0]
                second_half = split_link[-1][2::]
                bet_id = f"{first_half}#{second_half}"
                selections.append({
                    "id": bet_id
                })
            else:
                selections.append({
                    "id": link.get("bet_id")
                })

        return selections



    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            selections = self.format_selections()

            length_of_bet = len(selections)

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method="POST",
                headers=self.book_data.headers,
                payload={
                    "oddsStyle": "american",
                    "selections": selections
                },
            )

            api_data = self.check_api_response(sportsbook="draftkings", results=api_data)
            if not api_data:
                return

            if api_data and isinstance(api_data, dict):
                if not api_data.get("combinabilityRestrictions"):
                    sgp_odds_list = api_data.get("bets", [])
                    if isinstance(sgp_odds_list, list):
                        sgp_bet = next((bet for bet in sgp_odds_list if len(bet.get("selectionsMapped")) == length_of_bet), None)
                        if sgp_bet:
                            return {
                                "decimal": None,
                                "american": float(str(sgp_bet.get("displayOdds")).replace("−", "-"))
                            }

            return None


if __name__ == "__main__":
    import asyncio

    links = [
        "https://sportsbook.draftkings.com/event/33091930?outcomes=0OU82125316U22450_3", # Under 224.5 Points
        "https://sportsbook.draftkings.com/event/33091930?outcomes=0QA289645770%23396885360_13L42648Q11799469575Q20", # Carlton Carrington Over 1.5 Threes
        "https://sportsbook.draftkings.com/event/33098659?outcomes=0QA289707272%23397018721_13L42133Q1-80079547Q20", # dAKOTA JOSHUA ATGS
        "https://sportsbook.draftkings.com/event/33098659?outcomes=0HC82112228P150_3", # Over 7.5
    ]

    draftkings_sgp = Draftkings_SGP(links)
    data = asyncio.run(draftkings_sgp.run_book())
    print(data)