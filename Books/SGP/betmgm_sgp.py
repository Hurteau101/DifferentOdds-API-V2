import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
from Redis.redis_manager import RedisAsyncManager

class BetmgmSGP(SGPBookBase):
    def __init__(self, sgp_data: dict):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="betmgm", sgp_data=sgp_data)

    async def _get_cached_ids(self):
        redis_instance = RedisAsyncManager(database=self.redis_database)
        return await redis_instance.get_data(key_name="betmgm_ids")

    @SGPBookBase.ensure_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_ids = await self._get_cached_ids()

            if not mapped_ids:
                return None

            payload = self._create_payload(mapped_ids)
            with open("betmgm_sgp_payload.json", "w") as file:
                import json
                json.dump(payload, file, indent=2)

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

        odds_section = next(iter(api_data["betBuilderPricingGroups"].values()))
        if not odds_section:
            return None

        odds = odds_section.get("odds")

        if not odds or odds_section.get("suspensionState") == "MarketSuspended":
            return None

        return {
            "american": float(odds.get("americanOdds")),
            "decimal": float(odds.get("odds")),
        }

    def _create_payload(self, mapped_data):
        return {
            "tv1Picks": [
                {
                    "fixtureId": data.get("event_id"),
                    "gameId": int(mapped_data.get(str(-int(data.get("bet_id"))), {}).get("game_id")) if mapped_data.get(
                        str(-int(data.get("bet_id"))), {}).get("game_id") else None,
                    "resultId": -int(data.get("bet_id")),
                    "useLiveFallback": False,
                    "pickGroupId": mapped_data.get(str(-int(data.get("bet_id"))), {}).get("group_id"),
                }
                for data in self.link_data
            ],
        }
