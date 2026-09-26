import asyncio
import re

from curl_cffi import AsyncSession as CurlAsyncSession
from fastapi import params
from prompt_toolkit.application import current

from Bases.mapper_base import MapperBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from jsonpath_ng import parse
from datetime import datetime, timedelta, UTC
from itertools import batched


class PlaynowMapper(MapperBase):
    ACCEPTED_LEAGUES = ["NBA", "NFL", "NHL", "MLB", "WNBA", "ATP", "WTA", "UFC", "NCAAF", "NCAAB", "ATP TOUR", "WTA TOUR"]
    SPECIAL_SPLIT_KEYWORDS = ["to"]

    def __init__(self):
        super().__init__(book_name="playnow", category="sgp")

    async def _extract_event_ids(self, league_ids: list, session: CurlAsyncSession, max_advance_days: int = 7):
        current_date = datetime.now(UTC)

        days = [
            (current_date + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0).strftime(
                "%Y-%m-%dT%H:%M:%SZ")

            for day in range(max_advance_days + 1)
        ]

        day_str = ','.join(days)

        tasks = [
            self.api_caller(
                url=self.book_data.mapping.url.get("event_id_url"),
                session=session,
                method="GET",
                params={
                    "allowedEventSorts": "MTCH",
                    "includeChildMarkets": True,
                    "includeCommentary": True,
                    "includeMedia": True,
                    "drilldownTagIds": league_id,
                    "useMarketGroupCodeCombis": True,
                    "dates": day_str,
                    "lang": "en-US",
                    "channel": "I"
                }
            )

            for league_id in league_ids

        ]

        results = await asyncio.gather(*tasks)
        results = [result for result in results if result]

        return set(
            market.get("eventId")
            for result in results
            for data in result.get("data", {}).get("timeBandEvents")
            for event in data.get("events", [])
            for market in event.get("markets", [])
            if market.get("active") and market.get("eventId")
        )

    async def get_event_data(self, event_ids: list, session: CurlAsyncSession):
        chunked_event_ids = list(batched(event_ids, 10))

        tasks = [
            self.api_caller(
                url=self.book_data.mapping.url.get("game_url"),
                session=session,
                method="GET",
                params={
                    "eventIds": ','.join(event_ids),
                    "includeChildMarkets": True,
                    "includeCollections": True,
                    "lang": "en-US",
                    "channel": "I"
                }
            )

            for event_ids in chunked_event_ids

        ]

        events = []

        results = await asyncio.gather(*tasks)

        # Move all groups of events into 1 list.
        for result in results:
            if result:
                has_event = result.get("data", {}).get("events", [])
                if has_event:
                    events.extend(has_event)

        import json
        with open("playnow_events_NEW.json", "w") as file:
            json.dump(results, file, indent=2)

        self._extract_event_data(events)

    def _extract_event_data(self, events: list):
        stat_mapping = self.static_mapping_manager.get("static_mapping") or {}
        event_data = {}
        market_names_set = set()

        for event in events:
            if any([event.get("started", True), event.get("liveNow", True), event.get("resulted", True)]):
                continue

            teams = [
                team.get("name")
                for team in event.get("teams")
            ]

            if not teams:
                continue

            event_id = event.get("id")
            league = event.get("type", {}).get("name", '')
            game_key = " vs ".join(sorted(teams))
            start_time = event.get("startTime")

            game_key = f"{game_key}_{start_time}".replace(" ", "_").lower()

            game_bucket = event_data.setdefault(game_key, {})

            for market in event.get("markets", []):
                if market.get("status") != "ACTIVE":
                    continue

                group_code = market.get("groupCode", '')
                is_player = True if "player" in group_code.lower() else False
                raw_market_name = market.get("name")
                raw_market_name = re.sub(r"\s*\([^)]*\)", "", raw_market_name).strip() # Remove any () and anything inside.
                market_names_set.add(raw_market_name)
                line = market.get("handicapValue")

                for outcome in market.get("outcomes", []):
                    direction = outcome.get("name")
                    match = re.search(r"\d+", direction)
                    if match:
                        line = int(match.group()) - 0.5
                        direction = "Over"

                    if is_player:
                        player_market_name = " ".join(group_code.lower().replace("_", " ").replace("undefined", "").split())
                        market_name_split = player_market_name.split(" ")

                        market_name_split.insert(0, *self.SPECIAL_SPLIT_KEYWORDS)
                        pattern = r"\s*\b(?:" + "|".join(map(re.escape, market_name_split)) + r")\b\s*" # Remove all words in the market name split from the raw market name
                        player_name, *_ = re.split(pattern, raw_market_name, maxsplit=1, flags=re.IGNORECASE)
                        print(player_name)
                        # if player_name == "Spencer":
                        #     print(raw_market_name)
                        #     print(player_market_name)

                        # print("======")
                        # # print(player_name)
                        # print(player_name)
                        # # print(player_market_name)
                        # print("=======")

                        # raw_market_name, *rest = re.split(r"\s*over/under\s*", raw_market_name, maxsplit=1, flags=re.IGNORECASE)
                        # pattern = r"\b(?:" + "|".join(map(re.escape, player_market_name.split(" "))) + r")\b"
                        # result = re.sub(pattern, "", raw_market_name, flags=re.IGNORECASE)
                        # player_name = re.sub(r"\s+", " ", result).strip()


                        # Brian Robinson Jr Total Rushing Yards Over/Under 22.5
                        # TOTAL_RUSHING_YARDS_OVER_UNDER_PLAYER
                        # group_code_split = group_code.split("_")
                        # pattern = r"\b(?:" + "|".join(map(re.escape, group_code_split)) + r")\b"
                        # raw_market_name = re.sub(pattern, "", raw_market_name, flags=re.IGNORECASE)
                        # raw_market_name = re.sub(r"[/\d]", "", raw_market_name)
                        # market_name = re.sub(r"\s+", " ", raw_market_name).strip()
                        #
                        #
                        # print(market_name)


                        # has_over_under_name = OU_REGEX.search(market_name)
                        # if has_over_under_name:
                        #     market_name = market_name[:has_over_under_name.start()]
                        #
                        # player_market_name = group_code.lower().replace("player_undefined", "").replace("_", " ").strip()
                        #
                        # player_name = market_name.lower().replace(player_market_name, '')
                        #
                        # market_name = stat_mapping.get(player_market_name.lower(), player_market_name).lower()
                        #
                        # if market_name == "total passing yards over under player":
                        #     print(market_name)
                        #     print(player_market_name)


                        # prop_key = self.build_prop_key(stat=market_name, side=direction, line=str(line), player=player_name)
                        # game_bucket.setdefault(prop_key, {
                        #     "id": event_id,
                        #     "league": league
                        # })



        import json
        with open("playnow_mapper.json", "w") as file:
            json.dump(event_data, file, indent=2)
        # for m in market_names_set:
        #     print(m)







    async def run_mapper(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            raw_league_ids = await self.api_caller(
                session=session,
                url=self.book_data.mapping.url.get("league_id_url"),
                method="GET",
                params={
                    "drilldownNodeIds": 2,
                    "eventState": "OPEN_EVENT",
                    "includeMarketGroupCodeCombis": True,
                    "lang": "en-US",
                    "channel": "I"
                }
            )

            if not raw_league_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No league mapping IDs found"
                )
                return False

            league_ids = [
                m.value.get("refRecordId")
                for m in parse("$..drilldownNodes[*]").find(raw_league_ids)
                if m.value.get("name", "").upper() in self.ACCEPTED_LEAGUES
            ]

            event_ids = await self._extract_event_ids(league_ids=league_ids, session=session)

            if not event_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No event IDs found"
                )
                return False

            await self.get_event_data(event_ids=list(event_ids), session=session)






if __name__ == "__main__":
    playnow = PlaynowMapper()
    asyncio.run(playnow.run_mapper())