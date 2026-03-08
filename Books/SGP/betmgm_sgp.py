import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType
from Monitoring.monitoring import create_sentry_message

class BetmgmSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, mapped_ids_redis_instance, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="betmgm",
                         sgp_data=sgp_data, mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)


    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        mapped_ids = await self.load_mapped_ids(key_name="betmgm_ids")

        if not mapped_ids:
            create_sentry_message(
                tag_key="betmgm",
                tag_value="no_mapping",
                message="No mapped IDs were found in SGP",
                level="error"
            )
            return None

        payload = self._create_payload(mapped_ids)

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            payload=payload
        )

        if not api_data:
            return

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

            mapped = mapped_data.get(str(-int(bet_id)), {}) or mapped_data.get(str(bet_id), {})
            # If it's not part of the SGP Eligibility, then we must check the parent section.
            # The parent section will contain the milestone. Example 2+, 3+ etc. This is already pre-mapped.
            # if not mapped.get("is_sgp_eligible"):
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
                        "resultId": -int(bet_id),
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
        async with aiohttp.ClientSession() as session:
            sgp_data = {'book_name': 'betmgm', 'links': [
                # "https://sports.{state}.betmgm.com/en/sports/events/19025410?options=6:36475-2689474-4040918&type=Single",
                "https://sports.{state}.betmgm.com/en/sports/events/19025410?options=6:36475-2689474-4040935&type=Single",
                "https://sports.{state}.betmgm.com/en/sports/events/19025410?options=19025410-1474076463--155984492&type=Single"]}

            redis_mapped = RedisAsyncManager(database=2)
            book = BetmgmSGP(mapped_ids_redis_instance=redis_mapped, sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())


# "https://sports.{state}.betmgm.com/en/sports/events/19025410?options=6:36475-2689474-4040918&type=Single",