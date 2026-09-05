from collections import Counter
from Books.Bases.mapper_base import MapperBase
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession

class UnderdogSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="underdog", sgp_data=sgp_data, optional_db=0, **kwargs)

    def _rebuild_additional_data(self, additional_data: list):
        """Rebuilds the additional data"""
        modified_data = []

        for data in additional_data:
            if data.get("prop_key"):
                modified_data.append({"prop_key": data.get("prop_key")})
            else:
                prop_key = MapperBase.build_prop_key(side=data.get("side"), line=data.get("line"), player=data.get("player"), stat=data.get("market_name"))
                modified_data.append({"prop_key": f"{prop_key}".lower()})

        return modified_data

    def _build_params(self, underdog_data: dict, additional_data: list) -> dict | None:
        event_name_count = Counter(item.get("event_name") for item in additional_data if item.get("event_name"))
        date_count = Counter(item.get("date") for item in additional_data if item.get("date"))

        if len(event_name_count) != 1 or len(date_count) != 1:
            return None

        additional_data = self._rebuild_additional_data(additional_data=additional_data)

        params = {}

        for index, data in enumerate(additional_data):
            found = next((
                odds
                for item in underdog_data.get("data", [])
                for odds in item.get("odds", [])
                if odds.get("prop_key") == data.get("prop_key")
            ), None)

            if not found:
                return None

            key_id = found.get("optional_stats", {}).get("player_id")

            if not key_id:
                return None

            params.update({
                f'options[{index}][id]': key_id,
                f'options[{index}][type]': 'OverUnderOption',
            })

        params.update({
            'features[]': '2026-american-odds:display-only',
            'product': 'fantasy',
            'state_config_id': '8176bf5b-d026-4be0-b6b8-02f1f101a8c6'
        })

        return params

    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        underdog_data = await self.optional_redis_instance.get_data("underdog:base")
        additional_data = self.sgp_data.get("event_data", [])

        if not underdog_data or not additional_data:
            return None

        params = self._build_params(underdog_data=underdog_data, additional_data=additional_data)

        if not params:
            return None

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            params=params,
            method=self.book_data.method,
            headers=self.book_data.headers,
        )

        if not api_data or not api_data.get("status") == "valid":
            return None

        odds_dict = api_data.get("odds", {})
        american_odds = odds_dict.get("american")

        if not american_odds:
            return None

        return UnderdogSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=odds_dict.get("decimal")
        )



if __name__ == "__main__":
    import asyncio

    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                'book_name': 'underdog',
                'links': [
                    "",
                    "",
                ],
                "event_data": [
                    {
                        "market_name": "Player Strikeouts",
                        "date": "2026-09-01T00:10:00Z",
                        "event_name": "Houston Astros vs Chicago White Sox",
                        "line": "5.5",
                        "player": "Peter Lambert",
                        "side": "Over",
                        "prop_key": "5.5_over_peter_lambert_player_strikeouts",
                        "event_key": "chicago_white_sox_vs_houston_astros_2026-09-01t00:10:00z"
                    },
                    {
                        "market_name": "Player Bases",
                        "date": "2026-09-01T00:10:00Z",
                        "event_name": "Houston Astros vs Chicago White Sox",
                        "line": "0.5",
                        "player": "Colson Montgomery",
                        "side": "Over",
                        "prop_key": "0.5_colson_montgomery_over_player_bases",
                        "event_key": "chicago_white_sox_vs_houston_astros_2026-09-01t00:10:00z"
                    }
                ]
            }

            book = UnderdogSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
