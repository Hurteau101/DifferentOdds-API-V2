import aiohttp
import asyncio
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase

class BetMGM_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="betmgm_sgp.log", sportsbook_name="betmgm", links=links)

    async def _get_cached_ids(self):
        redis = RedisManager(db=self.redis_db)
        mapped_ids = await redis.fetch_data("betmgm_ids")
        await redis.close()
        return mapped_ids

    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_ids = await self._get_cached_ids()

            if not mapped_ids:
                return None

            payload = self._create_payload(mapped_ids)

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("sgp_url"),
                method="POST",
                headers=self.book_data.headers,
                payload=payload
            )

            api_data = self.check_api_response(sportsbook="betmgm", results=api_data)
            if not api_data:
                return

            api_data.pop("success")

            return self._extract_odds(api_data)

    def _extract_odds(self, api_data):
        # Return SGP Odds
        if not api_data.get("betBuilderPricingGroups"):
            return None
        odds = next(iter(api_data["betBuilderPricingGroups"].values())).get("odds")

        if not odds:
            return None

        return {
            "american_odds": float(odds.get("americanOdds")),
            "decimal_odds": float(odds.get("odds")),
        }

    def _create_payload(self, mapped_data):
        return {
            "tv1Picks": [
                {
                    "fixtureId": data.get("event_id"),
                    "gameId": int(mapped_data.get(str(-int(data.get("bet_id"))), {}).get("game_id")) if mapped_data.get(str(-int(data.get("bet_id"))), {}).get("game_id") else None,
                    "resultId": -int(data.get("bet_id")),
                    "useLiveFallBack": False,
                    "pickGroupId": mapped_data.get(str(-int(data.get("bet_id"))), {}).get("group_id"),
                }
                for data in self.link_data
            ]
        }




if __name__ == "__main__":
    links = [
        "https://sports.{state}.betmgm.com/en/sports/events/18037345?options=18037345-1353346646--467397931&type=Single",
        "https://sports.{state}.betmgm.com/en/sports/events/18037345?options=18037345-1353346662--467397900&type=Single",
    ]


    betmgm = BetMGM_SGP(links)
    # import asyncio

    data = asyncio.run(betmgm.run_book())
    print(data)

