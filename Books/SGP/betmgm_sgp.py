import asyncio
from Books.Bases.sgp_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession
from loguru import logger

class BetmgmSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="betmgm", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        mapped_ids = await self.mapper_redis_manager.get_data(self.mapper_id_name)
        import json
        with open("betmgm_ids.json", "w") as f:
            json.dump(mapped_ids, f, indent=2)


        if not mapped_ids:
            logger.error("No mapped ids found")
            return None

        payload = self._create_payload(mapped_ids)

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            json=payload
        )

        if not api_data:
            return None

        return self._extract_odds(api_data)

    def _extract_odds(self, api_data: dict) -> None | dict:
        """Extract the SGP Odds"""

        if not api_data.get("betBuilderPricingGroups"):
            return None

        odds_section = next(iter(api_data["betBuilderPricingGroups"].values()))
        if not odds_section:
            return None

        odds = odds_section.get("odds")

        if not odds or odds_section.get("suspensionState") == "MarketSuspended":
            return None

        return BetmgmSGP.return_odds(
            american_odds=odds.get("americanOdds"),
            decimal_odds=odds.get("odds")
        )

    def _create_payload(self, mapped_data: dict) -> dict:
        picks = {
            "tv1Picks": [],
            "tv2Picks": [],
        }

        for data in self.link_data:
            bet_id = data.get("bet_id")
            if not bet_id:
                continue

            mapped = mapped_data.get(bet_id, {})
            # If it's not part of the SGP Eligibility, then we must check the parent section.
            # The parent section will contain the milestone. Example 2+, 3+ etc. This is already pre-mapped.
            if mapped.get("parent_data", {}):
                mapped = mapped.get("parent_data", {})
                bet_id = mapped.get("bet_id")

            if not mapped:
                continue


            if mapped.get("source") == "V1":
                picks["tv1Picks"].append(
                    {
                        "fixtureId": mapped.get("fixture_id") if mapped.get("source") == "V1" else mapped.get(
                            "fixture_id_v2"),
                        "gameId": int(mapped.get("game_id")) if mapped.get("game_id") else None,
                        "resultId": bet_id,
                        "useLiveFallback": False,
                        "pickGroupId": mapped.get("group_id"),
                    }
                )

            elif mapped.get("source") == "V2":
                picks["tv2Picks"].append(
                    {
                        "fixtureId": mapped.get("fixture_id_v2"),
                        "isClassicBetBuilder": False,
                        "optionId": bet_id,
                        "optionMarketId": mapped.get("game_id"),
                        "pickGroupId": mapped.get("group_id"),
                    }
                )

        return picks

if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {'book_name': 'betmgm', 'links': [
                "https://sports.{state}.betmgm.com/en/sports/events/19888186?options=2:7827687-203886485-779526886&type=Single",
                "https://sports.{state}.betmgm.com/en/sports/events/19888186?options=2:7827687-203886657-779527230&type=Single"
            ]}

            book = BetmgmSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())