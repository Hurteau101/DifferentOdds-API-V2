async def _get_mappings(self, session: aiohttp.ClientSession, event_ids: set):
    async def process_mapping(event_id, semaphore: asyncio.Semaphore):
        async with semaphore:
            results = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.mapping.url.get("event_details"),
                method=self.book_data.mapping.method,
                headers=self.book_data.mapping.headers,
                parse_json=True,
                payload={
                    "BrandId": 3,
                    "LanguageId": 25,
                    "ClientTypeId": 2,
                    "JurisdictionId": 2,
                    "ClientIntegratorId": 1,
                    "EventId": event_id,
                    "ScoreboardRequest": {
                        "IncidentRequest": {},
                        "ScoreboardType": 3
                    }
                }
            )

            return results if results else {}

    semaphore = asyncio.Semaphore(20)
    tasks = [process_mapping(event_id, semaphore) for event_id in event_ids]
    results = await asyncio.gather(*tasks)

    mapping_data = {}

    mapping = get_static_mapping()
    stat_mapping = mapping.get("stats", {})

    for result in results:
        if not result:
            continue

        raw_event_name = result.get("Event", {}).get("EventName")
        if not raw_event_name:
            continue

        event_name = raw_event_name.replace("-", "vs").lower()
        event_bucket = mapping_data.setdefault(event_name, {})

        markets = result.get("Markets", [])

        for market in markets:
            raw_market_name = market.get("Title").lower().replace("alternate", "").strip()
            cleaned_market_name = stat_mapping.get(raw_market_name, raw_market_name).lower()
            market_bucket = event_bucket.setdefault(cleaned_market_name, {})

            selection_list = market.get("Headers", [])
            outcome_list = market.get("Outcomes", [])[0]

            if not selection_list or not outcome_list:
                continue

            for selection, outcome in zip(selection_list, outcome_list):
                handicap = market.get("Handicap", 0.00)
                selection = selection.lower()

                if handicap != 0.00:
                    selection = f"{selection} {handicap}"

                selection_bucket = market_bucket.setdefault(selection, {})
                selection_bucket.update({"outcome_id": outcome})

    import json
    with open("mapping_test.json", "w") as file:
        json.dump(mapping_data, file, indent=2)