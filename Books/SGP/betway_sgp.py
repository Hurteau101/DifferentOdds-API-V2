import asyncio
import re
from typing import Counter
from curl_cffi import AsyncSession as CurlAsyncSession
from Bases.mapper_base import MapperBase
from Books.Bases.sgp_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import decimal_to_american

class BetwaySGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(category="SGP", book_name="betway", **kwargs)

    def _rebuild_additional_data(self, additional_data: list):
        """Rebuilds the additional data"""
        modified_data = []

        pattern = re.compile(r"event/(\d+)")

        event_id = next((
            found_id.group(1)
            for link in self.links
            if (found_id := pattern.search(link))
        ), None)


        for data in additional_data:
            if data.get("prop_key"):
                modified_data.append({"event_key": event_id, "prop_key": data.get("prop_key")})
            else:
                prop_key = MapperBase.build_prop_key(side=data.get("side"), line=data.get("line"), player=data.get("player"), stat=data.get("market_name"))
                modified_data.append({"event_key": event_id, "prop_key": f"{prop_key}".lower()})


        return modified_data

    def _build_outcomes(self, mapped_ids: dict, additional_data: list) -> list | None:
        event_name_count = Counter(item.get("event_name") for item in additional_data if item.get("event_name"))
        date_count = Counter(item.get("date") for item in additional_data if item.get("date"))

        if len(event_name_count) != 1 or len(date_count) != 1:
            return None

        additional_data = self._rebuild_additional_data(additional_data=additional_data)
        outcomes = []

        for data in additional_data:
            event_key = data.get("event_key")
            prop_key = data.get("prop_key")

            found = mapped_ids.get(event_key, {}).get(prop_key)
            if not found:
                return None

            outcomes.append(found.get("outcome_id"))

        return outcomes

    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)

        additional_data = self.sgp_data.get("event_data", [])

        if not mapped_ids or not additional_data:
            return None

        outcome_ids = self._build_outcomes(mapped_ids=mapped_ids, additional_data=additional_data)

        if not outcome_ids:
            return None

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            json={
                "BrandId": 3,
                "LanguageId": 25,
                "ClientTypeId": 2,
                "JurisdictionId": 2,
                "ClientIntegratorId": 1,
                "Selections": [
                    {
                        "OutcomeId": outcome
                    }
                    for outcome in outcome_ids
                ],
                "Rewards": []
            }
        )

        if not api_data or not isinstance(api_data, dict) or api_data.get("UnavailableOutcomeIds"):
            return None

        bets = api_data.get("Bets")

        if not bets or not isinstance(bets, list):
            return None

        selection_group = bets[0]
        decimal_odds = selection_group.get("BetPrice", {}).get("dec")

        selections = selection_group.get("Selections", [])

        if len(outcome_ids) != len(selections) or not decimal_odds:
            return None

        american_odds = decimal_to_american(float(decimal_odds))

        return BetwaySGP.return_odds(
            american_odds=american_odds,
            decimal_odds=float(decimal_odds)
        )


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {
                'book_name': 'betway',
                'links': [
                    "https://{state}.betway.com/sports/event/17158909",
                    "https://{state}.betway.com/sports/event/17158909"
                ],
                "event_data": [
                  {
                    "market_name": "Player RBIs",
                    "date": "2026-08-30T23:20:00Z",
                    "event_name": "Chicago Cubs vs Cincinnati Reds",
                    "line": "1.5",
                    "player": "JJ Bleday",
                    "side": "Over",
                    "prop_key": "1.5_jj_bleday_over_player_rbis",
                    "event_key": "chicago_cubs_vs_cincinnati_reds_2026-08-30t23:20:00z"
                  },
                    {
                        "market_name": "Player Bases",
                        "date": "2026-08-30T23:20:00Z",
                        "event_name": "Chicago Cubs vs Cincinnati Reds",
                        "line": "0.5",
                        "player": "Pete Crow-Armstrong",
                        "side": "Over",
                        "prop_key": "0.5_over_pete_crow-armstrong_player_bases",
                        "event_key": "chicago_cubs_vs_cincinnati_reds_2026-08-30t23:20:00z"
                    }
                ]
            }

            book = BetwaySGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
