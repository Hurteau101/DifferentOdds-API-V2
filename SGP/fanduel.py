import asyncio
import json
import time

import aiohttp
from orjson import orjson

from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase

class Fanduel_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC, log_directory="SGP Logs", log_name="fanduel_sgp.log", sportsbook_name="fanduel", links=links)
        self.VALID_LEAGUES = [
            "mlb", "nfl", "ncaaf", "sport", "wnba", "tennis", "pga", "ufc", "esports", "nba", "ncaab", "nhl"
        ]

    @SGPBookBase.require_link_data
    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            mapped_data = await self._map_data()

            # Check if mapped_data is empty or contains None marketId
            if not mapped_data or any(data for data in mapped_data if data.get("marketId") is None):
                return None

            payload = self._create_payload(mapped_data)

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("sgp_url"),
                method="POST",
                headers=self.book_data.headers,
                payload=payload
            )


            if not api_data:
                return None

            return self._extract_odds(api_data)

    def _extract_odds(self, api_data):
        # Find Dict that holds the SGM - As these are the SGP odds.
        odds_dict = next((
            sgp
            for bet_keys, bet_values in api_data.items()
            if bet_values and isinstance(bet_values, list)
            for sgp in bet_values
            if sgp.get("isSGM")
        ), None)


        # Ensure that the SGP odds passed in match the SGP calculated. Fanduel will still return SGP odds with picks removed.
        sgp_length = len(self.link_data)
        if not odds_dict or len(odds_dict.get("legCombinations", [])) != sgp_length or not odds_dict.get("winAvgOdds"):
            return None

        return {
            "american_odds": float(odds_dict.get("winAvgOdds").get("americanDisplayOdds", {}).get("americanOdds")),
            "decimal_odds": odds_dict.get("winAvgOdds").get("decimalDisplayOdds", {}).get("decimalOdds"),
        }

    async def _map_data(self):
        """ Map the marketID from the links to the actual marketId using Redis. Due to links being external market IDs"""
        mapped_ids = await self._returned_mapped_redis_data("fanduel_ids")

        if isinstance(mapped_ids, bytes):
            mapped_ids = orjson.loads(mapped_ids)
        if isinstance(mapped_ids, str):
            mapped_ids = json.loads(mapped_ids)

        if not mapped_ids:
            self.file_logger.log(
                message="No mapped IDs found in Redis",
                level="ERROR",
            )

            return None



        return [
            {
                "marketId": mapped_ids.get(f"{data.get('event_id')}-{data.get('bet_id')}", None),
                # "marketId": f"{data.get('event_id')}-{data.get('bet_id')}",
                "selectionId": int(data.get("bet_id")),
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

    # Extract all the event id's from each league result
    def _extract_league_ids(self, league_results):
        event_ids = set()

        for league_data in league_results:
            if not league_data:
                continue

            for coupon in league_data.get("layout", {}).get("coupons", {}).values():
                if coupon.get("eventId"):
                    event_ids.add(coupon["eventId"])

                for display in coupon.get("display", []):
                    for row in display.get("rows", []):
                        if row.get("eventId"):
                            event_ids.add(row["eventId"])

        return event_ids

    # Get the league data ids for each league.
    async def _get_league_data_ids(self):
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("league_id_url").format(league=league),
                    method=self.book_data.method,
                    headers=self.book_data.headers
                )
                for league in self.VALID_LEAGUES
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                self._api_call_log("fanduel_sgp")
                return

            return self._extract_league_ids(results)

    # Map the external ID's to the actual market ids. We use the external as the key for quick reference for SGP call later on.
    def _extract_actual_market_id(self, event_data):
        external_market_ids = {}

        for result in event_data:
            if not result:
                continue

            for market_id, sgp_data in result.get("attachments", {}).get("markets", {}).items():
                external_id = next((
                    sgp.get("externalMarketId") for sgp in sgp_data.get("associatedMarkets")
                ), None)

                if external_id:
                    for selection in sgp_data.get("runners"):
                        selection_id = selection.get("selectionId")
                        if selection_id:
                            key = f"{external_id}-{selection_id}"
                            external_market_ids[key] = market_id

        return external_market_ids

    # Extract all the actual market ids for the SGP from the event ids.
    async def _get_actual_market_id_data(self, event_ids):
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("market_id_url").format(event_id=event_id),
                    method=self.book_data.method,
                    headers=self.book_data.headers
                )

                for event_id in event_ids
            ]

            results = await asyncio.gather(*tasks)
            if not results:
                self._api_call_log("fanduel_sgp")
                return

            return self._extract_actual_market_id(results)

    # Store the mapped IDs in Redis for quick access later on.
    async def store_fanduel_data(self):
        """Extract all the main map ID's needed for Fanduel SGP for mapping. ID's are stored in Redis for quick access later on."""
        event_ids = await self._get_league_data_ids()
        mapped_ids = await self._get_actual_market_id_data(event_ids)

        if mapped_ids:
            redis = RedisManager(db=2, max_connections=1)
            await redis.store_data(
                key_name="fanduel_ids",
                data_to_store=mapped_ids,
                key_expiration=600
            )
            await redis.close()




if __name__ == "__main__":
    links = [
        "https://sportsbook.fanduel.com/addToBetslip?marketId=42.535745385&selectionId=26999348",# Total Runs Over 9.5 --  Braves / Mets
        # "https://sportsbook.fanduel.com/addToBetslip?marketId=42.524340163444&selectionId=12493614",
        # "https://sportsbook.fanduel.com/addToBetslip?marketId=42.52434016333&selectionId=12493614",
        "https://sportsbook.fanduel.com/addToBetslip?marketId=42.535745385&selectionId=27163247" # Moneyline Braves  -- Braves / Mets
    ]
    fanduel = Fanduel_SGP(links=links)
    import asyncio


    run_type = ""

    if run_type == "store":
        asyncio.run(fanduel.store_fanduel_data())
    else:
        asyncio.run(fanduel.run_book())



