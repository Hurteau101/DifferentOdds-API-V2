import asyncio
import re
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Books.Bases.mapper_base import MapperBase
from curl_cffi import AsyncSession as CurlAsyncSession
from datetime import datetime, timezone

PLAYER_PATTERN = re.compile(r"\s*\(([^()]{1,4})\)")
MILESTONE_REGEX = re.compile(r"player to\s+.*?(?:(\d+)\s*\+|\ban?\b)\s+(.+)", re.IGNORECASE)
STAT = re.compile(r'^(?:.*\d+\+|player to (?:record|hit)(?:\s+an?\b)?)\s*',re.IGNORECASE)


class BovadaMapper(MapperBase):
    SPORT_PATHS = [
        "baseball/mlb",
        "basketball/nba",
        "basketball/wnba",
        "hockey/nhl",
        "football/nfl",
        "football/college-football"
    ]


    def __init__(self):
        super().__init__(book_name="bovada", category="sgp")
        self.static_mapper = self.static_mapping.get("static_mapping", {})


    def _extract_other_stat_types(self, stat_type_original: str, bucket: dict, market: dict, outcomes: list) -> tuple | None:
        if PLAYER_PATTERN.search(stat_type_original):
            cleaned = PLAYER_PATTERN.sub("", stat_type_original).strip()
            new_stat_type, player_name = cleaned.split(" - ")
            stat_type = self._check_period(market=market, stat_type=new_stat_type)
            stat_type = self.static_mapper.get(new_stat_type.lower(), stat_type)

            if player_name:
                stat_type = f"player {stat_type}"

            for outcome in outcomes:
                side = outcome.get("description")
                line = outcome.get("price", {}).get("handicap", None)

                prop_key = self.build_prop_key(stat=stat_type, side=side, line=str(line) if line else None, player=player_name)
                bucket.setdefault(prop_key, {
                    "id": outcome.get("id"),
                })
        else:
            stat_type_split = stat_type_original.split(" - ")

            # Skip 3 way's
            if len(stat_type_split) <= 1:
                return

            new_stat_type, side = stat_type_split[0], stat_type_split[1]
            stat_type = self._check_period(market=market, stat_type=new_stat_type)
            stat_type = self.static_mapper.get(new_stat_type.lower(), stat_type)

            for outcome in outcomes:
                line = outcome.get("price", {}).get("handicap", None)

                prop_key = self.build_prop_key(stat=stat_type, side=side, line=str(line) if line else None, player=None)
                bucket.setdefault(prop_key, {
                    "id": outcome.get("id"),
                })


    def _extracted_milestone(self, original_stat_type: str, outcomes: list, bucket: dict) -> bool:
        """Handles the case where the stat type is a milestone."""
        has_milestone = MILESTONE_REGEX.search(original_stat_type)
        if has_milestone:
            milestone_value = has_milestone.group(1)

            for outcome in outcomes:
                raw_player_name = outcome.get("description")
                player_name = PLAYER_PATTERN.sub("", raw_player_name).strip()
                raw_stat_name = STAT.sub('', original_stat_type).strip()
                stat_name = self.static_mapper.get(raw_stat_name.lower(), raw_stat_name)

                if player_name:
                    stat_name = f"player {stat_name}"

                prop_key = self.build_prop_key(
                    stat=stat_name,
                    side="over",
                    line=str(float(milestone_value) - 0.5) if milestone_value else str(0.5),
                    player=player_name
                )

                bucket.setdefault(prop_key, {
                    "id": outcome.get("id"),
                })

            return True

        return False

    def _check_period(self, market: dict, stat_type: str):
        """Adds period to stat type if not game."""
        period = market.get("period", {}).get("description").lower()
        if period != "game":
            return f"{period} {stat_type}"

        return stat_type

    async def run_mapper(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            tasks = [
                self.api_caller(
                    session=session,
                    headers=self.book_data.mapping.headers,
                    url=f"{self.book_data.mapping.url.get('main_url')}{path}",
                    method=self.book_data.mapping.method,
                )
                for path in self.SPORT_PATHS
            ]

            results = await asyncio.gather(*tasks)
            filtered_results = [
                event
                for outer in results
                if outer
                for result in outer
                if result
                for event in result.get("events", [])
                if not event.get("live")
            ]

            if not filtered_results:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No filtered mapping found"
                )

                return False

            mapped_ids = {}

            for event in filtered_results:
                start_time = event.get("startTime")
                parsed_utc = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc)
                game_date = parsed_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

                if not game_date:
                    continue

                team_names = [
                    competitor.get("name")
                    for competitor in event.get("competitors", [])
                    if competitor.get("name")
                ]

                link = event.get("link", '')
                league = link.split('/')[2]

                team_name_key = '_vs_'.join(sorted(team_names))
                game_key = f"{team_name_key}_{game_date}".replace(" ", "_").lower()


                for group in event.get("displayGroups", []):
                    for market in group.get("markets", []):
                        if not market.get("availableSGP"):
                            continue

                        bucket = mapped_ids.setdefault(game_key, {})
                        original_stat_type = market.get("description")

                        # If - not in stat type, then the side will just be the description.
                        if "-" not in original_stat_type:
                            is_extracted = self._extracted_milestone(original_stat_type=original_stat_type, outcomes=market.get("outcomes", []), bucket=bucket)
                            if is_extracted:
                                continue

                            for outcome in market.get("outcomes", []):
                                side = outcome.get("description")
                                line = outcome.get("price", {}).get("handicap", None)

                                special_stat_type = self._special_mapping(mapping_name=original_stat_type, league=league)
                                stat_type = self._check_period(market=market, stat_type=special_stat_type)
                                stat_type = self.static_mapper.get(stat_type.lower(), stat_type)

                                prop_key = self.build_prop_key(stat=stat_type, side=side, line=str(line) if line else None, player=None)
                                bucket.setdefault(prop_key, {
                                    "id": outcome.get("id"),
                                })
                        else:
                            self._extract_other_stat_types(stat_type_original=original_stat_type, bucket=bucket, market=market, outcomes=market.get("outcomes", []))


            if not mapped_ids:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MAPPING,
                    error_message="No mapping found"
                )

                return False

            await self.store_data(
                key_name=self.mapper_id_name,
                data_to_store=mapped_ids,
                expiration_time=900
            )

            return True


if __name__ == "__main__":
    bovada = BovadaMapper()
    asyncio.run(bovada.run_mapper())
