import aiohttp

from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase
from itertools import chain

class BetMGM_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="betmgm_sgp.log", sportsbook_name="betmgm", links=links)
        self.VALID_LEAGUE_IDS = [
            23, # Baseball
            11, # Football
        ]

    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_ids = await self._returned_mapped_redis_data("betmgm_ids")
            if not mapped_ids:
                return None
            payload = self._create_payload(await self._returned_mapped_redis_data("betmgm_ids"))

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("sgp_url"),
                method="POST",
                headers=self.book_data.headers,
                payload=payload
            )

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
                    "gameId": int(mapped_data.get(str(-int(data.get("bet_id"))), {}).get("game_id")),
                    "resultId": -int(data.get("bet_id")),
                    "useLiveFallBack": False,
                    "pickGroupId": mapped_data.get(str(-int(data.get("bet_id"))), {}).get("group_id"),
                }
                for data in self.link_data
            ]
        }

    def _filter_mapping(self, raw_data):
        # Map the ID's
        return {
            str(option.get("id")): {
                "game_id": option_list.get("id"),
                "group_id": data.get("addons", {}).get("betBuilderId"),
            }

            for data in raw_data.get("fixtures", [])
            for option_list in data.get("optionMarkets", [])
            for option in option_list.get("options", [])
        }

    async def _extract_mapping(self):
        # Get all the mapping ID's for the leagues we want.
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_id_url").format(league_id=league_id),
                    method="GET",
                    headers=self.book_data.headers
                )
                for league_id in self.VALID_LEAGUE_IDS
            ]

            results = await asyncio.gather(*tasks)
            if not results:
                self._api_call_log("betmgm_sgp")
                return

            return dict(
                chain.from_iterable(self._filter_mapping(result).items() for result in results if result)
            )


    async def store_betmgm_data(self):
        mapped_ids = await self._extract_mapping()

        if mapped_ids:
            redis = RedisManager(db=self.redis_db, max_connections=1)
            await redis.store_data(
                key_name="betmgm_ids",
                data_to_store=mapped_ids,
                key_expiration=600
            )

            await redis.close()



if __name__ == "__main__":
    links = [
        "https://sports.{state}.betmgm.com/en/sports/events/18037345?options=18037345-1353346646--467397931&type=Single",
        "https://sports.{state}.betmgm.com/en/sports/events/18037345?options=18037345-1353346662--467397900&type=Single",
    ]


    betmgm = BetMGM_SGP(links)
    import asyncio

    run_type = ""

    if run_type == "store":
        asyncio.run(betmgm.store_betmgm_data())
    else:
        data = asyncio.run(betmgm.run_book())
        print(data)

