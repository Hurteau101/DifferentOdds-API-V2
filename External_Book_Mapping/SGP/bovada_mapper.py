import asyncio
import itertools
import re
import time

import aiohttp
from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import clean_structure
from Utils.request_caller import SportbookRequestType

def get_static_mapping():
    return static_mapping_service.get()

class BovadaMapper(BaseMapper):
    SPORT_PATHS = [
        "baseball/mlb",
        "basketball/nba",
        "hockey/nhl",
        "football/nfl",
        "football/college-football"
    ]


    def __init__(self):
        super().__init__(book_name="bovada", category="sgp", request_type=SportbookRequestType.ASYNC)

    def _determine_market_type(self, teams: set, group_description: str, market_name: str):
        """Determines if its a main market or player market"""
        keywords = ["player", "milestone"]

        if group_description == "game lines" or group_description == "game props":
            return False

        if any(keyword in group_description for keyword in keywords):
            return True

        if any(keyword in market_name for keyword in keywords):
            return True

        if "-" in market_name and not any(team in market_name for team in teams):
            return True


    def _special_mapping(self, custom_id: str):
        mapping = {
            "baseball": {
                "total": "total runs",
                "spread": "runline",
            },
            "hockey": {
                "total": "total goals",
                "spread": "puckline",
            },
            "basketball": {
                "total": "total points",
            }
        }

        return next((
            market_mappings
            for sport, market_mappings in mapping.items()
            if sport in custom_id
        ), {})




    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager) -> bool:
        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
                    "Referer": "https://www.bovada.lv/sports",
                },
                url=f"{self.book_data.mapping.url.get('main_url')}{path}",
                method=self.book_data.mapping.method,
            )
            for path in self.SPORT_PATHS
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        filtered_results = [
            event
            for outer in results
            for result in outer
            if result
            for event in result.get("events", [])
            if not event.get("live")
        ]

        # print(results)
        # import json
        # with open("bovada_results.json", "w") as file:
        #     json.dump(filtered_results, file, indent=4)

        # results = results[0]
        if not filtered_results:
            return False

        mapped_ids = {}

        for event in filtered_results:
            custom_id = event.get("link", '')
            custom_id = re.sub(r"^\/", "", custom_id)  # Remove leading slash if it exists.
            mapping = self._special_mapping(custom_id)

            if not custom_id:
                continue

            team_names = {
                name.lower()
                for competitor in event.get("competitors", [])
                for name in [competitor.get("name", ""), competitor.get("shortName", "")]
            }


            for group in event.get("displayGroups", []):
                group_description = group.get("description", '').lower()

                for market in group.get("markets", []):
                    if not market.get("availableSGP"):
                        continue

                    raw_market_name = market.get("description", '').lower().replace("o/u", "").strip()
                    raw_market_name = mapping.get(raw_market_name.lower(), raw_market_name)
                    is_player_market = self._determine_market_type(teams=team_names,
                                                                   group_description=group_description, market_name=raw_market_name)

                    # These markets have the player name attached to them.
                    # We can separate the player name from the market name by splitting on the dash and taking the first part as the market name.
                    if is_player_market and "player" not in raw_market_name:
                        raw_market_name = f"player {raw_market_name.split('-')[0].strip()}"

                    period = market.get("period", {}).get("description").lower()
                    period_abbreviation = market.get("period", {}).get("abbreviation", '').lower()

                    if period != "game":
                        raw_market_name = f"{period} {raw_market_name}"

                    is_team_market = not is_player_market and "-" in raw_market_name and any(
                        team in raw_market_name for team in team_names)

                    # Remove any parentheses and any content within the parentheses.
                    # Also cleans the name.
                    cleaned_market_name = re.sub(r'\s*\(.*?\)', '', clean_structure(raw_market_name)).strip()

                    for outcome in market.get("outcomes", []):
                        outcome_id = outcome.get("id")
                        selection = outcome.get("description", '').lower()

                        # Remove any parentheses and any content within the parentheses from selection name.
                        selection = re.sub(r'\s*\(.*?\)', '', selection).strip()

                        # Remove period from selection name
                        if period_abbreviation in selection or period in selection:
                            selection = re.sub(rf'\s*-\s*\b{period_abbreviation}\b', '', selection).strip()
                            selection = re.sub(rf'\s*-\s*\b{period}\b', '', selection).strip()

                        line = outcome.get("price", {}).get("handicap", None)

                        outcome_description = outcome.get("description", '').lower()
                        player_name = market.get("descriptionKey", '').split("-")[-1].lower().strip()

                        if is_team_market:
                            if "-" in cleaned_market_name:
                                cleaned_market_name = cleaned_market_name.split("-")[0].strip()


                        if line:
                            # Remove trailing 0, example 216.0
                            line = re.sub(r"\.0\b", "", line)


                            selection = f"{selection} {line}"

                            if is_player_market:
                                # Outcome description contains the over/under information.
                                selection = f"{player_name} {outcome_description} {line}"
                            elif is_team_market:
                                cleaned_market_name = f"team {cleaned_market_name}" if "team" not in cleaned_market_name else cleaned_market_name

                                team_id = outcome.get("competitorId", "")
                                team = next((
                                    team.get("name", '').lower()
                                    for team in event.get("competitors", [])
                                    if team.get("id") == team_id
                                ), "N/A")

                                selection = f"{team} {selection}"

                        if not line and (re.search(r'\bto\b', outcome_description) or re.search(r'\bplayer to\b', cleaned_market_name)):
                            # For certain milestones like record 2+ hits, they don't have the player name where it usually is
                            if "-" not in market.get("descriptionKey", ''):
                                player_name = re.sub(r'\s*\(.*?\)', '', outcome_description).strip()

                            # Find digits before + (Ex. to make 4+ threes) - Milestone Lines.
                            found_line = re.search(r'(\d+)\+', outcome.get("description", '')) or re.search(r'(\d+)\+', cleaned_market_name)
                            if found_line:
                                # Displayed line.
                                displayed_line = float(found_line.group(1))

                                # We need to subtract it by 0.5 so that it is displayed as 3.5 instead of 4 for the example above.
                                # This is because the line is usually displayed as "over 3.5 threes" instead of "over 4 threes".
                                line = displayed_line - 0.5
                                selection = f"{player_name} over {line}"

                            else:
                                # If there is no line, we can just display it as "over" with 0.5. (Ex. player to hit a homerun)
                                selection = f"{player_name} over 0.5"

                        market_name = get_static_mapping().get("stats", {}).get(cleaned_market_name,
                                                                                cleaned_market_name).lower()
                        mapped_ids.setdefault(custom_id, {}).setdefault(market_name, {}).setdefault(selection, outcome_id)


        # stat_types = set(
        #     stat_type
        #     for game in mapped_ids.values()
        #     for stat_type in game.keys()
        # )

        await redis_instance.store_data(
            key_name="bovada_ids",
            data_to_store=mapped_ids,
            key_expiration=900
        )


if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = BovadaMapper()
    async def main():
        async with aiohttp.ClientSession() as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())
