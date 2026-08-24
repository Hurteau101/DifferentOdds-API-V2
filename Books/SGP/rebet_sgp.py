import asyncio

from aiohttp import payload
from Books.Bases.sgp_book_base import SGPBookBase



class RebetSGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(category="SGP", book_name="rebet", sgp_data={}, **kwargs)

    def _build_payload(self, mapped_ids: dict, additional_data: dict) -> dict:
        payload = {
            "event_id": None,
            "selections": []
        }

        for data in additional_data:
            event_name = data.get("event_name")
            market_name = data.get("market_name").lower()
            selection = data.get("selection").lower() if isinstance(data.get("selection"), str) else data.get("selection")

            split_event_name = event_name.split(" vs ")
            sorted_event_name = " vs ".join(sorted(split_event_name)).lower()

            print("Event Name: ", sorted_event_name)
            print("Market Name: ", market_name)
            print("Selection: ", selection)

            found_id = mapped_ids.get(sorted_event_name, {}).get(market_name.lower())
            print(found_id)
            if not found_id:
                continue

            payload["event_id"] = found_id.get("event_id")

            selections = {
                "market_id": found_id.get("market_id"),
                "outcome_id": found_id.get(selection),
            }

            specifier = found_id.get("specifier")

            if specifier:
                selections.update({
                    "specifiers": found_id.get("specifier"),
                })

            payload["selections"].append(selections)


        return payload

    async def run_book(self, session):
        additional_data = self.extras.get("additional_data")
        valid_input = all(
            all(data.get(key) for key in ("event_name", "market_name", "selection"))
            for data in additional_data
        )

        mapped_ids = await self.load_mapped_ids(key_name="rebet_ids")

        if not mapped_ids:
            return

        payload = self._build_payload(mapped_ids=mapped_ids, additional_data=additional_data)

        import json
        print(json.dumps(payload, indent=2))

        if len(payload["selections"]) != len(additional_data):
            return

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers=self.book_data.headers,
            json=payload
        )

        if not all([api_data, api_data.get("success"), api_data.get("data", {}).get("combined_odds")]):
            return None

        decimal_odds = float(api_data.get("data", {}).get("combined_odds"))
        print(decimal_odds)

        american_odds = RebetSGP.convert_decimal_to_american(decimal_odds=decimal_odds)
        return RebetSGP.return_odds(
            american_odds=american_odds,
            decimal_odds=decimal_odds
        )



# Need to pass:
# 1. Event Name (Sorted)
# 2. Market Type (Moneyline)
# 3. Market Name (Wizards)

if __name__ == "__main__":
    book = RebetSGP(additional_data=[
        {"event_name": "Washington Wizards vs Houston Rockets", "market_name": "Moneyline",
         "selection": "Washington Wizards"},
        {"event_name": "Washington Wizards vs Houston Rockets", "market_name": "Total Points", "selection": "Over 224.5"}
    ])
    data = asyncio.run(book.run_book())
    print(data)