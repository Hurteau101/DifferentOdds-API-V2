import asyncio
import json
import aiohttp
from orjson import orjson
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase

class Fanduel_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="fanduel_sgp.log", sportsbook_name="fanduel", links=links)

    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_data = await self._map_data()

            # Check if mapped_data is empty or contains None marketId
            if not mapped_data or any(data for data in mapped_data if data.get("marketId") is None):
                return None

            payload = self._create_payload(mapped_data)

            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("sgp_url"),
                method="POST",
                headers=self.book_data.headers,
                payload=payload
            )

            api_data = self.check_api_response(sportsbook="fanduel", results=raw_api_data)
            if not api_data:
                return

            api_data.pop("success")

            number_of_legs = len(mapped_data)

            return self._extract_odds(api_data, number_of_legs)

    def _extract_odds(self, api_data, leg_number):
        # Find Dict that holds the SGM - As these are the SGP odds.
        # odds_dict = next((
        #     sgp
        #     for bet_keys, bet_values in api_data.items()
        #     if bet_values and isinstance(bet_values, list)
        #     for sgp in bet_values
        #     if sgp.get("isSGM")
        # ), None)

        # for bet_keys, bet_values in api_data.items():
        #     print(bet_values)

        odds_dict = next((
            sgp
            for bet_keys, bet_values in api_data.items()
            for sgp in bet_values
            if sgp.get("legCombinations")
               and len(sgp.get("legCombinations")) == leg_number
               and sgp.get("winAvgOdds")
        ), None)

        if not odds_dict:
            return None

        # Ensure that the SGP odds passed in match the SGP calculated. Fanduel will still return SGP odds with picks removed.
        # sgp_length = len(self.link_data)
        # if not odds_dict or len(odds_dict.get("legCombinations", [])) != sgp_length or not odds_dict.get("winAvgOdds"):
        #     return None
        #
        return {
            "american": float(odds_dict.get("winAvgOdds").get("americanDisplayOdds", {}).get("americanOdds")),
            "decimal": odds_dict.get("winAvgOdds").get("decimalDisplayOdds", {}).get("decimalOdds"),
        }

    async def _map_data(self):
        """ Map the marketID from the links to the actual marketId using Redis. Due to links being external market IDs"""
        redis = RedisManager(db=self.redis_db)
        mapped_ids = await redis.fetch_data("fanduel_ids")

        if isinstance(mapped_ids, bytes):
            mapped_ids = orjson.loads(mapped_ids)
        if isinstance(mapped_ids, str):
            mapped_ids = json.loads(mapped_ids)

        if not mapped_ids:
            self.file_logger.log(
                sportsbook="fanduel",
                message="No mapped IDs found in Redis",
                level="ERROR",
            )

            return None

        return [
            {
                "marketId": mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("market_id"),
                "selectionId": mapped_ids.get(f"{data.get('event_id')}_{data.get('bet_id')}", {}).get("selection_id"),
            }
            for data in self.link_data
        ]



    def _create_payload(self, payload_data):
        return {
            "betLegs": [
                {
                    "legType": "SIMPLE_SELECTION",
                    "betRunners": [
                        {
                            "runner": {
                                "marketId": str(leg.get("marketId")),
                                "selectionId": int(leg.get("selectionId")),
                            }
                        }
                    ]
                }

                for leg in payload_data
            ]
        }


if __name__ == "__main__":
    links = [
        "https://sportsbook.fanduel.com/addToBetslip?marketId=42.538760977&selectionId=16593214", # Under 91.5
        "https://sportsbook.fanduel.com/addToBetslip?marketId=42.538760961&selectionId=16195884", # AYTD
        "https://sportsbook.fanduel.com/addToBetslip?marketId=42.504353914&selectionId=50199", # Justin Barron ATGS
        # "https://sportsbook.fanduel.com/addToBetslip?marketId=42.539367630&selectionId=49501370" # Nick Perbix ATGS
    ]
    fanduel = Fanduel_SGP(links=links)
    odds = asyncio.run(fanduel.run_book())
    print(odds)


