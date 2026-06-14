import asyncio
import os
import re
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType
from Utils.proxy_manger import ProxyManager
from curl_cffi import AsyncSession as CurlAsyncSession


class CaesarsSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, mapped_ids_redis_instance, auth_redis_instance, **kwargs):
        super().__init__(request_type=SportbookRequestType.SPOOF, category="SGP", book_name="caesars",
                         sgp_data=sgp_data, mapped_ids_redis_instance=mapped_ids_redis_instance,
                         auth_redis_instance=auth_redis_instance, **kwargs)
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

    def _create_actual_mapping(self, line_data: dict, link_data: dict, mapped_ids: dict) -> dict:
        """Create the actual mapping for a single link data entry."""
        line = self._add_lines(
            line_data=line_data,
            link_data=link_data,
            mapped_ids=mapped_ids
        )

        mapped_entry = {
            "selectionId": mapped_ids.get(link_data.get("select_id"), {}).get("selection_id"),
            "eventId": mapped_ids.get(link_data.get("select_id"), {}).get("event_id"),
            "marketId": mapped_ids.get(link_data.get("select_id"), {}).get("market_id"),
            "stakePerLine": 0,
        }

        if line is not None:
            mapped_entry["line"] = line

        return mapped_entry


    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        auth_token_data = await self.load_auth_token(key_name="caesars_waf_token")

        if not auth_token_data:
            return None

        waf_token = auth_token_data.get("waf_token")
        cookie_str = auth_token_data.get("cookie_str")
        proxy_index = auth_token_data.get("proxy_index")
        proxy_str = auth_token_data.get("proxy_str")


        if not all([waf_token is not None, cookie_str is not None, proxy_index is not None, proxy_str is not None]):
            create_sentry_message(
                tag_key="caesars",
                tag_value="no_auth",
                message="Couldn't find WAF token in redis",
                level="error"
            )
            return False

        line_data = self._lines_extraction(self.lines if self.lines else {})

        mapped_ids = await self.load_mapped_ids(key_name="caesar_mapped_ids")

        if not mapped_ids:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="mapping_failure",
                message="No mapped IDs were found.",
                level="error"
            )
            return None

        mapped_data = [
            self._create_actual_mapping(
                line_data=line_data,
                link_data=data,
                mapped_ids=mapped_ids
            )
            for data in self.link_data
        ]

        if not mapped_data or any(data for data in mapped_data if
                                  not any([data.get("marketId"), data.get("selectionId"), data.get("eventId")])):
            return None

        payload = self._create_payload(mapped_data)

        # proxy = os.getenv("CAESAR_PROXIES")
        #
        # if not proxy:
        #     create_sentry_message(
        #         tag_key="caesars",
        #         tag_value="proxy_failure",
        #         message="No proxy found",
        #         level="error"
        #     )
        #     return

        # proxies = proxy.split(",")
        # proxy_manager = ProxyManager(proxies=proxies, api_caller_func=self.api_caller)
        proxy_manager = ProxyManager(api_caller_func=self.api_caller)


        # raw_api_data = await proxy_manager.proxy_caller(
        #     book_name=self.book_data.name,
        #     session=session,
        #     url=self.book_data.url.get("main_url"),
        #     method=self.book_data.method,
        #     headers={**self.book_data.mapping.headers,
        #              "x-aws-waf-token": waf_token,
        #              "Cookie": cookie_str},
        #     payload=payload,
        #     parse_json=True
        # )

        raw_api_data = await proxy_manager.rotating_proxy_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("main_url"),
            method=self.book_data.method,
            headers={**self.book_data.mapping.headers,
                     "x-aws-waf-token": waf_token,
                     "Cookie": cookie_str},
            payload=payload,
            parse_json=True,
            max_retries=10,
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
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {
                "book_name": "caesars",
                "links": [
                    "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=f1a06cf7-57a7-3550-90f4-01b6b69ce94b",
                    "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=935c7b73-6120-385a-adac-402b97a2876b",
                ],
            }

            redis_mapped = RedisAsyncManager(database=2)
            redis_instance = RedisAsyncManager(database=5)
            book = CaesarsSGP(mapped_ids_redis_instance=redis_mapped, auth_redis_instance=redis_instance, sgp_data=sgp_data)
            data = await book.run_book(session=session)
            if data:
                print(data)

    asyncio.run(main())
