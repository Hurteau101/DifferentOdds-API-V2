import asyncio
from collections import Counter
from Books.Bases.sgp_base import SGPBookBase
from Books.Bases.mapper_base import MapperBase
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import decimal_to_american
from curl_cffi import AsyncSession as CurlAsyncSession
from Books.SGP.Mapping.prop_builder_mapper import PropBuilderMapper


class PropBuilderSGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(category="SGP", book_name="prop builder", **kwargs)

    def _rebuild_additional_data(self, additional_data: list):
        """Rebuilds the additional data"""
        modified_data = []

        for data in additional_data:
            if data.get("prop_key") and data.get("event_key"):
                modified_data.append({"event_key": data.get("event_key"), "prop_key": data.get("prop_key")})
            else:
                split_event_name = data.get("event_name").split(" vs ")
                event_name = "_vs_".join(sorted(split_event_name)).replace(" ", "_").lower()
                event_date = data.get("date")
                event_key = "_".join([event_name, event_date]).replace(" ", "_").lower()
                prop_key = MapperBase.build_prop_key(side=data.get("side"), line=data.get("line"), player=data.get("player"), stat=data.get("market_name"))

                modified_data.append({"event_key": event_key, "prop_key": f"{prop_key}".lower()})


        return modified_data

    def _build_payload(self, mapped_ids: dict, additional_data: list) -> dict | None:
        event_name_count = Counter(item.get("event_name") for item in additional_data if item.get("event_name"))
        date_count = Counter(item.get("date") for item in additional_data if item.get("date"))

        if len(event_name_count) != 1 or len(date_count) != 1:
            return None

        additional_data = self._rebuild_additional_data(additional_data=additional_data)

        payload = {
            "events": []
        }

        for data in additional_data:
            event_key = data.get("event_key")
            prop_key = data.get("prop_key")
            found = mapped_ids.get(event_key, {}).get(prop_key)
            if not found:
                return None

            payload["events"].append({
                "player1": found.get("player1"),
                "game1": found.get("game1"),
                "statistic": found.get("statistic"),
                "conditionValue": found.get("condition_value"),
                "type": found.get('type') or 20,
                "market": found.get("game_id"),
            })

        return payload


    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)

        additional_data = self.sgp_data.get("event_data", [])
        if not mapped_ids or not additional_data:
            return None

        payload = self._build_payload(mapped_ids=mapped_ids, additional_data=additional_data)
        if not payload:
            return None

        token = await PropBuilderMapper.security_token(session=session,
                                                 security_url=self.book_data.mapping.url.get("security_url"),
                                                 api_caller=self.api_caller)
        if not token:
            return None

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method=self.book_data.method,
            headers={
                **self.book_data.headers,
                **token

            },
            valid_codes=[201],
            json=payload
        )

        if not api_data:
            return None

        odds = api_data.get("data", {}).get("odds")

        if not odds:
            return None

        american_odds = decimal_to_american(float(odds))

        return PropBuilderSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=float(odds)
        )



if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                'book_name': 'prop_builder',
                'links': [
                    "https://{state}.betway.com/sports/event/16902972",
                    "https://{state}.betway.com/sports/event/16902972",
                ],
                "event_data": [
                      {
                        "market_name": "Total Runs",
                        "date": "2026-08-30T02:05:00Z",
                        "event_name": "Oakland Athletics vs Baltimore Orioles",
                        "line": "11.5",
                        "player": "",
                        "side": "Under",
                        # "prop_key": "11.5_total_runs_under",
                        # "event_key": "baltimore_orioles_vs_oakland_athletics_2026-08-30t02:05:00z"
                      },
                      {
                        "market_name": "Moneyline",
                        "date": "2026-08-30T02:05:00Z",
                        "event_name": "Oakland Athletics vs Baltimore Orioles",
                        "line": "",
                        "player": "",
                        "side": "Baltimore Orioles",
                        # "prop_key": "baltimore_orioles_moneyline",
                        # "event_key": "baltimore_orioles_vs_oakland_athletics_2026-08-30t02:05:00z"
                      }
                    ]
            }

            book = PropBuilderSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
