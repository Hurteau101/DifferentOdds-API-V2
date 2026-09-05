import asyncio
import re
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.Bases.sgp_base import SGPBookBase

class CaesarsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="caesars", sgp_data=sgp_data,  **kwargs)
        self.lines = sgp_data.get("lines")

    def _create_payload(self, mapped_link_data: list) -> dict:
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

    def _lines_extraction(self, lines_dict: dict) -> dict | None:
        """Extract line data from the provided lines dictionary."""
        line_data = {}

        for link, line in lines_dict.items():
            selection_id = re.search(self.book_data.regex.get("select_id"), link)
            if not selection_id:
                return None

            if line == 0.5:
                line = None

            line_data[selection_id.group(1)] = line

        return line_data

    def _add_lines(self, line_data: dict, link_data: dict, mapped_ids: dict) -> float:
        """Add lines to the mapped data based on link data and line data."""
        selection = link_data.get("select_id")

        if line_data:
            line = line_data.get(selection)
            return float(line) if line is not None else None

        return float(mapped_ids.get(selection, {}).get("line")) if mapped_ids.get(selection, {}).get("line") is not None else None

    def _create_actual_mapping(self, link_data: dict, mapped_ids: dict) -> dict:
        """Create the actual mapping for a single link data entry."""
        # line = self._add_lines(
        #     line_data=line_data,
        #     link_data=link_data,
        #     mapped_ids=mapped_ids
        # )

        mapped_entry = {
            "selectionId": mapped_ids.get(link_data.get("select_id"), {}).get("selection_id"),
            "eventId": mapped_ids.get(link_data.get("select_id"), {}).get("event_id"),
            "marketId": mapped_ids.get(link_data.get("select_id"), {}).get("market_id"),
            "stakePerLine": 0,
        }

        # if line is not None:
        #     mapped_entry["line"] = line

        return mapped_entry


    @SGPBookBase.ensure_link_data
    async def run_book(self, session):
        waf_token = await self.auth_redis_manager.get_data(self.auth_id_name)

        if not waf_token:
            return None

        # line_data = self._lines_extraction(self.lines if self.lines else {})

        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)

        if not mapped_ids:
            return None

        mapped_data = [
            self._create_actual_mapping(
                link_data=data,
                mapped_ids=mapped_ids
            )
            for data in self.link_data
        ]

        print(mapped_data)

        if not mapped_data or any(data for data in mapped_data if
                                  not any([data.get("marketId"), data.get("selectionId"), data.get("eventId")])):
            return None

        payload = self._create_payload(mapped_data)

        raw_api_data = await self.api_caller(
            use_proxy=True,
            url=self.book_data.url.get("main_url"),
            method=self.book_data.method,
            headers={**self.book_data.mapping.headers,
                     "x-aws-waf-token": waf_token},
            json=payload,
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
                "american": parlay.get("price", {}).get("american"),
            }
            for parlay in raw_api_data.get("parlays", [])
            if not "error" in parlay or not len(parlay.get("errors")) > 0
        ), None)


        return CaesarsSGP.return_odds(american_odds=odds.get("american"),decimal_odds=odds.get("decimal")) if odds else None


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                "book_name": "caesars",
                "links": [
                    "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=4705a2d8-8250-3a27-ae98-ffe76f2956bf",
                    "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=bac348d4-03a7-309a-bcac-df1bb4b55829",
                ],
            }

            book = CaesarsSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
