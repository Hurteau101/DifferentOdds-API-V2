import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase


class Novig_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="novig_sgp.log", sportsbook_name="novig", links=links)

    @staticmethod
    def convert_probability_to_american_odds(probability_str):
        """Converts a probability (as a string) to American odds."""
        probability = float(probability_str)

        if not 0 <= probability <= 1:
            raise None

        if probability == 0:
            return None
        if probability == 1:
            return None

        if probability > 0.5:
            american_odds = -(100 * probability) / (1 - probability)
        else:
            american_odds = (100 * (1 - probability)) / probability

        return round(american_odds)

    def _extract_odds(self, api_data):
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

        return Novig_SGP.convert_probability_to_american_odds(probability)


    @SGPBookBase.require_link_data
    async def run_book(self):
        ids = [{"id": link.get("bet_id")} for link in self.link_data]
        payload = {
            "boostId": None,
            "outcomes": ids
        }


        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method="POST",
                payload=payload
            )


            if not api_data:
                self._api_call_log("novig_sgp")

            if api_data and isinstance(api_data, list):
                data = self._extract_odds(api_data)
                if data:
                    return {
                        "american_odds": float(data),
                    }

            return None



if __name__== "__main__":
    import asyncio

    links = [
        "https://app.novig.us/events/e16296cb-9ca6-4582-ad93-1625db5de588/oddsjam",
        "https://app.novig.us/events/5ed4a9e7-67f3-4a8b-bbfc-368c7a0a38c4/oddsjam"
    ]

    novig_sgp = Novig_SGP(links=links)
    data = asyncio.run(novig_sgp.run_book())
    print(data)