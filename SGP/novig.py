import aiohttp
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase
import asyncio

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
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method="POST",
                payload=payload
            )

            api_data = self.check_api_response(sportsbook="novig", results=raw_api_data)
            if not api_data:
                return

            api_data.pop("success")

            if api_data and isinstance(api_data.get("data"), list):
                data = self._extract_odds(api_data.get("data"))
                if data:
                    return {
                        "american": float(data),
                    }

            return None



if __name__== "__main__":
    links = [
        "https://app.novig.us/events/1726a9eb-50ae-492a-be36-93ae3bd68cf5/oddsjam", # RAMS -2.5
        "https://app.novig.us/events/edc6d463-3632-4377-8bfc-94778a95109c/oddsjam", # Over 51.5
    ]

    novig_sgp = Novig_SGP(links=links)
    data = asyncio.run(novig_sgp.run_book())
    print(data)