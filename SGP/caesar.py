import json
import re

import aiohttp
from orjson import orjson
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase
import asyncio
from SGP.Mapper.caesar_mapper import Caesar_Mapper

### PASS IN A LINE INSTEAD OF USING MAPPER, THIS WILL PREVENT IT FROM USING THE WRONG LINE IN API CALL.


class Caesars_SGP(SGPBookBase):
    def __init__(self, links, lines: dict = None, **kwargs):
        self.lines = lines
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="caesars_sgp.log", sportsbook_name="caesars", links=links, **kwargs)

    def _create_payload(self, mapped_link_data: list):
        return {
            "legs": [
                link_data
                for link_data in mapped_link_data
            ],
            "combinationSelections": [],
            "includeMultiLine": False,
            "channel": "desktop",
            "channelDetail": "cordova-desktop",
        }

    async def _mapped_data(self):
        redis_client = RedisManager(db=self.redis_db)
        mapped_ids = await redis_client.fetch_data("caesars_ids")

        if isinstance(mapped_ids, bytes):
            mapped_ids = orjson.loads(mapped_ids)
        if isinstance(mapped_ids, str):
            mapped_ids = json.loads(mapped_ids)

        if not mapped_ids:
            self.file_logger.log(
                sportsbook="caesars",
                message="No mapped IDs found in Redis",
                level="ERROR",
            )

            return None


        return [
            {
                "selectionId": mapped_ids.get(data.get("bet_id"), {}).get("selection_id"),
                "eventId": mapped_ids.get(data.get("bet_id"), {}).get("event_id"),
                "marketId": mapped_ids.get(data.get("bet_id"), {}).get("market_id"),
                "stakePerLine": 0,
                **({"line": mapped_ids.get(data.get("line"), {}).get("line")} if mapped_ids.get(data.get("line"), {}).get("line") is not None else {})

            }
            for data in self.link_data
        ]

    def _lines_extraction(self, lines_dict: dict):
        """Extract line data from the provided lines dictionary."""
        line_data = {}

        for link, line in lines_dict.items():
            selection_id = re.search(self.book_data.regex.get("bet_id_regex"), link)
            if not selection_id:
                return None

            line_data[selection_id.group(1)] = line

        return line_data

    def _add_lines(self, mapped_data: dict, line_data: dict, link_data: dict):
        """Add lines to the mapped data based on link data and line data."""
        selection = link_data.get("bet_id")

        if line_data:
            line = line_data.get(selection)
            return float(line) if line is not None else None

        return float(mapped_data.get(selection, {}).get("line")) if mapped_data.get(selection, {}).get("line") is not None else None


    def _create_actual_mapping(self, mapped_data: dict, line_data: dict, link_data: dict):
        """Create the actual mapping for a single link data entry."""
        line = self._add_lines(
            mapped_data=mapped_data,
            line_data=line_data,
            link_data=link_data,
        )

        mapped_entry = {
            "selectionId": mapped_data.get(link_data.get("bet_id"), {}).get("selection_id"),
            "eventId": mapped_data.get(link_data.get("bet_id"), {}).get("event_id"),
            "marketId": mapped_data.get(link_data.get("bet_id"), {}).get("market_id"),
            "stakePerLine": 0,
        }

        if line is not None:
            mapped_entry["line"] = line

        return mapped_entry

    @SGPBookBase.require_link_data
    async def run_book(self):
        redis_waf = RedisManager(db=5)
        waf_token = await redis_waf.get_auth_token("caesars_sgp_waf_token")
        await redis_waf.close()

        if not waf_token:
            print("No WAF Token")
            return


        line_data = self._lines_extraction(self.lines if self.lines else {})
        ceasar_mapping = Caesar_Mapper(waf_token)
        mapped_ids = await ceasar_mapping.run_book()

        if not mapped_ids:
            print("No mapped IDs")
            return None

        mapped_data = [
            self._create_actual_mapping(
                mapped_data=mapped_ids,
                line_data=line_data,
                link_data=data
            )
            for data in self.link_data
        ]

        if not mapped_data or any(data for data in mapped_data if not any([data.get("marketId"), data.get("selectionId"), data.get("eventId")])):
            print("No mapped data")
            return None

        payload = self._create_payload(mapped_data)

        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers={**self.book_data.headers, "x-aws-waf-token": waf_token},
                payload=payload
            )

            if not raw_api_data or not raw_api_data.get("parlays", []):
                return None

            errors = next((
                parlay.get("errors")
                for parlay in raw_api_data.get("parlays", [])
            ), 0)

            if errors and len(errors) > 0:
                return None

            odds = next((
                {
                    "decimal": parlay.get("price", {}).get("decimal"),
                    "american": float(parlay.get("price", {}).get("american")),
                }
                for parlay in raw_api_data.get("parlays", [])
                if not "error" in parlay or not len(parlay.get("errors")) > 0
            ), None)

            return odds if odds else None


if __name__ == "__main__":
    links = [
        "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=03ea80fc-6859-3ccf-acf9-7346d56bca06", # 0.5
        "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=9cde3b80-4348-3f94-991e-3f2068c6475c" # 7.5
    ]


    additional_information = {
        "lines": {
            "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=03ea80fc-6859-3ccf-acf9-7346d56bca06": 10.5,
            "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=9cde3b80-4348-3f94-991e-3f2068c6475c": None
        }
    }

    caesar_sgp = Caesars_SGP(links=links, additional_info=additional_information)
    odds = asyncio.run(caesar_sgp.run_book())
    print(odds)