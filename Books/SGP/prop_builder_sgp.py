import asyncio
from collections import Counter

from sentry_sdk.integrations import aiohttp

from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType
from Utils.helpers import cache_time

class PropBuilderSGP(SGPBookBase):
    def __init__(self, mapped_ids_redis_instance, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="prop_builder",
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)

    def _build_payload(self, mapped_ids: dict, additional_data: dict) -> dict:
        event_name_count = Counter(item.get("event_name") for item in additional_data if item.get("event_name"))
        date_count = Counter(item.get("date") for item in additional_data if item.get("date"))

        if len(event_name_count) != 1 or len(date_count) != 1:
            return {}

        event_name = additional_data[0].get("event_name")
        event_date = cache_time(additional_data[0].get("date"))

        team_1, team_2 = event_name.split(" vs ")

        if not team_1 or not team_2:
            return {}

        team_key = " vs ".join(sorted([team_1, team_2]))
        event_key = "_".join([team_key, event_date]).replace(" ", "_").lower()

        found_game_mapping = mapped_ids.get(event_key, {})

        if not found_game_mapping:
            print("No Game Mapping Found:", event_key)
            return {}

        payload = {
            "events": []
        }

        for additonal in additional_data:
            selection_name = additonal.get("selection_name")
            market_name = additonal.get("market_name", '')

            parts = [selection_name, market_name]
            if market_name.lower() == "moneyline":
                parts.reverse()

            key_name = "_".join(parts).lower().replace(" ", "_").replace("_team_total", "")
            found_key = found_game_mapping.get(key_name)

            if not found_key:
                break

            payload["events"].append({
                "player1": found_key.get("player1"),
                "game1": found_key.get("game1"),
                "statistic": found_key.get("statistic"),
                "conditionValue": found_key.get("condition_value"),
                "type": found_key.get('type') or 20,
                "market": found_key.get("game_id"),
            })

        if len(payload.get("events")) != len(additional_data):
            return {}

        return payload


    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        print("RUNNING PROPBUILDER")
        mapped_ids = await self.load_mapped_ids(key_name="prop_builder_mapped_ids")
        additional_data = self.sgp_data.get("event_data", [])

        if not mapped_ids or not additional_data:
            return None

        payload = self._build_payload(mapped_ids=mapped_ids, additional_data=additional_data)

        if not payload:
            return None

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method=self.book_data.method,
            headers=self.book_data.headers,
            payload=payload
        )

        if not api_data:
            return None

        odds = api_data.get("data", {}).get("odds")

        if not odds:
            return None

        american_odds = self.convert_decimal_to_american(float(odds))

        return PropBuilderSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=float(odds)
        )



if __name__ == "__main__":
    async def main():
        async with aiohttp.ClientSession() as session:
            sgp_data = {
                'book_name': 'prop_builder',
                'links': [
                    "https://{state}.betway.com/sports/event/16902972",
                    "https://{state}.betway.com/sports/event/16902972",
                ],
                "event_data": [
                    {
                        "event_name": "Los Angeles Sparks vs Indiana Fever",
                        "date": "2026-07-09 02:00:00Z",
                        "market_name": "Player Points",
                        "selection_name": "Erica Wheeler Over 8.5",
                        "line": "8.5"
                    },
                    {
                        "event_name": "Los Angeles Sparks vs Indiana Fever",
                        "date": "2026-07-09 02:00:00Z",
                        "market_name": "Player Points + Rebounds + Assists",
                        "selection_name": "Dearica Hamby Under 26.5",
                        "line": "26.5"
                    }
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            book = PropBuilderSGP(sgp_data=sgp_data, mapped_ids_redis_instance=redis_mapped)
            data = await book.run_book(session=session)
            print(data)

            ## Looks to be working for player props.  Will have to test on Auto SGP and fix game markets.

    asyncio.run(main())
