import asyncio
import re
from typing import Counter

from Bases.mapper_base import MapperBase
from Books.Bases.sgp_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class BovadaSGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(category="SGP", book_name="bovada", **kwargs)

    def _rebuild_additional_data(self, additional_data: list):
        """Rebuilds the additional data"""
        modified_data = []

        for data in additional_data:
            if data.get("prop_key") and data.get("event_key"):
                modified_data.append({"event_key": data.get("event_key"), "prop_key": data.get("prop_key")})
            else:
                split_event_name = data.get("event_name").split(" vs ")
                event_name = "_vs_".join(sorted(split_event_name)).replace(" ", "_").lower()
                event_date = data.get("date")
                event_key = "_".join([event_name, event_date]).replace(" ", "_").lower()
                prop_key = MapperBase.build_prop_key(side=data.get("side"), line=data.get("line"), player=data.get("player"), stat=data.get("market_name"))

                modified_data.append({"event_key": event_key, "prop_key": f"{prop_key}".lower()})


        return modified_data

    def _build_params(self, mapped_ids: dict, additional_data: list) -> dict | None:
        event_name_count = Counter(item.get("event_name") for item in additional_data if item.get("event_name"))
        date_count = Counter(item.get("date") for item in additional_data if item.get("date"))

        if len(event_name_count) != 1 or len(date_count) != 1:
            return None

        additional_data = self._rebuild_additional_data(additional_data=additional_data)
        outcomes = {
            "outcomeId": []
        }

        for data in additional_data:
            event_key = data.get("event_key")
            prop_key = data.get("prop_key")

            found = mapped_ids.get(event_key, {}).get(prop_key)
            if not found:
                return None

            outcome_id = found.get("id")
            if not outcome_id:
                return None

            outcomes["outcomeId"].append(f"A:{outcome_id}")

        return outcomes



    @SGPBookBase.ensure_link_data
    async def run_book(self, session) -> dict | None:
        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)
        additional_data = self.sgp_data.get("event_data", [])

        if not mapped_ids or not additional_data:
            return None

        params = self._build_params(mapped_ids=mapped_ids, additional_data=additional_data)

        if not params:
            return None


        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method=self.book_data.method,
            headers=self.book_data.headers,
            params=params,
            default_headers=False
        )

        if not api_data:
            return None

        sgp_dict = next((
            bet
            for api in api_data.get("bets", {}).values()
            for bet in api
            if bet.get("description", '').lower() == "same game parlay bet"
        ), {})

        if sgp_dict.get("numWays") !=  len(self.links):
            return None

        american_odds = sgp_dict.get("totalPriceFormattedMap", {}).get("AMERICAN")

        if not american_odds:
            return None

        return BovadaSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=sgp_dict.get("totalPriceFormattedMap", {}).get("DECIMAL")
        )


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                "book_name": "bovada",
                "links": [
                    "https://www.bovada.lv/sports/baseball/mlb/seattle-mariners-cleveland-guardians-202606261910",
                    "https://www.bovada.lv/sports/baseball/mlb/seattle-mariners-cleveland-guardians-202606261910",
                ],
                "event_data": [
                    {
                        "market_name": "Player Runs",
                        "date": "2026-09-01T22:45:00Z",
                        "event_name": "Boston Red Sox vs Seattle Mariners",
                        "line": "0.5",
                        "player": "Josh Naylor",
                        "side": "Over",
                        "prop_key": "0.5_josh_naylor_over_player_runs",
                        "event_key": "boston_red_sox_vs_seattle_mariners_2026-09-01t22:45:00z"
                    },
                    {
                        "market_name": "Player Runs",
                        "date": "2026-09-01T22:45:00Z",
                        "event_name": "Boston Red Sox vs Seattle Mariners",
                        "line": "0.5",
                        "player": "Caleb Durbin",
                        "side": "Over",
                        "prop_key": "0.5_caleb_durbin_over_player_runs",
                        "event_key": "boston_red_sox_vs_seattle_mariners_2026-09-01t22:45:00z"
                    }
                ]
            }

            book = BovadaSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)


    asyncio.run(main())

