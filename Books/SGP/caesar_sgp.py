import asyncio
import re

import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType


class DraftkingsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="caesars", sgp_data=sgp_data)
        self.lines = sgp_data.get("lines")


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

    def _lines_extraction(self, lines_dict: dict):
        """Extract line data from the provided lines dictionary."""
        line_data = {}

        for link, line in lines_dict.items():
            selection_id = re.search(self.book_data.regex.get("bet_id_regex"), link)
            if not selection_id:
                return None

            if line == 0.5:
                line = None

            line_data[selection_id.group(1)] = line

        return line_data

    def _add_lines(self, mapped_data: dict, line_data: dict, link_data: dict):
        """Add lines to the mapped data based on link data and line data."""
        selection = link_data.get("select_id")


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
            "selectionId": mapped_data.get(link_data.get("select_id"), {}).get("selection_id"),
            "eventId": mapped_data.get(link_data.get("select_id"), {}).get("event_id"),
            "marketId": mapped_data.get(link_data.get("select_id"), {}).get("market_id"),
            "stakePerLine": 0,
        }

        if line is not None:
            mapped_entry["line"] = line

        return mapped_entry


    @SGPBookBase.ensure_link_data
    async def run_book(self):
        redis_waf = RedisManager(db=5)
        waf_token = await redis_waf.get_auth_token("caesars_sgp_waf_token")
        await redis_waf.close()

        if not waf_token:
            print("No WAF Token")
            return

        line_data = self._lines_extraction(self.lines if self.lines else {})
        redis_client = RedisManager(db=2)
        mapped_ids = await redis_client.fetch_data(key_name="caesar_mapped_ids")

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

        if not mapped_data or any(data for data in mapped_data if
                                  not any([data.get("marketId"), data.get("selectionId"), data.get("eventId")])):
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


