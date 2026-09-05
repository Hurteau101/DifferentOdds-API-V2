import json
import os
from collections import defaultdict
from itertools import batched
import asyncio
import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.orm import sessionmaker
from Database.base_db import sync_engine
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Redis.redis_manager import RedisSyncManager
from Database.Sportsbooks.sportsbook_db import VerifiedStats, VerifiedTeams, VerifiedLeague, VerificationTeam, VerificationLeague, VerificationStats
from rapidfuzz import fuzz, process
from loguru import logger

load_dotenv()

NORMALIZE_PROMPT = """\
Normalize the given competitor to its official name, abbreviation, and league.

The competitor may be a team (e.g. 'Boston Celtics') or an individual athlete in a \
solo sport such as tennis, MMA, or golf.

Rules:
- Teams: use the full official team name (e.g. 'Boston Celtics', 'Manchester United'). \
Do NOT include 'University', 'College', or other institution names unless they are \
officially part of the team name.
- Individual athletes: use the official first and last name ONLY. No middle names, \
suffixes, or nicknames.
- 'abbreviation': the official team abbreviation. For individual athletes, return null.
- 'league': the specific competition or organization the competitor plays in \
(e.g. 'NFL', 'CFB', 'NHL', 'CBB', 'ATP', 'WTA', 'UFC', 'PGA', 'EPL', 'La Liga', \
'MLS', 'Bundesliga', 'Serie A', 'UEFA CL'). Do NOT use generic names like \
'BASKETBALL', 'HOCKEY', 'SOCCER', 'TENNIS', 'MMA', or 'FIFA'.
- For soccer, identify the exact league or competition based on the team name.
- If the league cannot be confidently determined, return null for 'league'.
- If the competitor cannot be identified, return null for 'normalized_name'.
- If the abbreviation cannot be identified, return null for 'abbreviation'.
- Limit to 1 web source.

Return your answer ONLY as a JSON object with keys 'normalized_name', 'abbreviation', and \
'league'. Do not wrap the JSON in code blocks or markdown.
"""


def extract_prompt(name: str, league: str) -> str:
    return (
        f"{NORMALIZE_PROMPT}\n"
        f"Team name: {name}\n"
        f"League: {league}"
    )

class VerificationMapping:
    def __init__(self):
        self.mapping_redis_manager = RedisSyncManager(database=9)
        self.session_factory = sessionmaker(bind=sync_engine())
        self.client = AsyncOpenAI(api_key=os.getenv("OPEN_AI_KEY"))

    def _check_verification_table(self, non_matched_data: list):
        """Check against verification table"""
        with self.session_factory() as db_session:
            stored_teams = VerificationTeam.get_mapping(db_session=db_session)

        return [
            non_match
            for non_match in non_matched_data
            if (non_match.get("received_name").lower(), non_match.get("original_league").upper()) not in stored_teams
        ]

    def update_stats_verification(self, stats: list):
        """Updates the verification stats table"""
        if not stats:
            return

        self.update_redis(redis_keys={f'stats:{stat.get("received_name")}' for stat in stats})
        with self.session_factory() as db_session:
            VerificationStats.update_mapping(db_session=db_session, stat_mapping=stats)

    def update_league_verification(self, leagues: list):
        """Updates the verification league table"""
        if not leagues:
            return

        self.update_redis(redis_keys={f'leagues:{stat.get("received_name")}' for stat in leagues})

        with self.session_factory() as db_session:
            VerificationLeague.update_mapping(db_session=db_session, league_mapping=leagues)

    def update_verified_teams(self, matched_teams: dict):
        """Updates the verified team table"""
        if not matched_teams:
            return

        matched_teams = list(matched_teams.values())

        with self.session_factory() as db_session:
            VerifiedTeams.update_mapping(db_session=db_session, team_mapping=matched_teams)

    def update_verification_teams(self, ai_teams: list):
        """Updates the verification team table"""
        if not ai_teams:
            return

        with self.session_factory() as db_session:
            VerificationTeam.update_mapping(db_session=db_session, team_mapping=ai_teams)

    def update_redis(self, redis_keys: list | set):
        """Removes the keys from redis"""
        if redis_keys:
            print(f"Deleting {redis_keys} keys from Redis")
            self.mapping_redis_manager.delete_keys(keys=redis_keys)

    # Use fuzzy matching to see if there is any very close matches, before passing to AI.
    def fuzzy_match(self, unmapped_data: list, mapped_keys: set, verified_teams: dict) -> dict:
        matched = {}
        non_matched = {}
        redis_keys = set()

        for data in unmapped_data:
            match = process.extractOne(
                query=data.get("name"),
                choices=mapped_keys,
                scorer=fuzz.ratio,
                score_cutoff=95,
            )

            if match:
                matched_str, score, d = match
                found_normalized = next((
                    verified
                    for verified in verified_teams.values()
                    if matched_str.lower() == verified.get("normalized_name").lower()
                ), None)

                if found_normalized:
                    redis_keys.add(data.get("redis_key"))
                    matched[(data.get("league"), data.get("name"))] = {
                        "received_name": data.get("name"),
                        "normalized_name": found_normalized.get("normalized_name"),
                        "abbreviation": found_normalized.get("abbreviation"),
                        "league": found_normalized.get("league"),
                    }

                continue

            non_matched[(data.get("league"), data.get("name"))] = {
                "sportsbook": data.get("book"),
                "original_league": data.get("league"),
                "received_name": data.get("name"),
                "redis_key": data.get("redis_key")
            }

        return {"matched": matched, "non_matched": non_matched, "redis_keys": redis_keys}

    # Use AI to help map some of the unmatched data.
    async def fetch_response(self, unmatch_data: dict) -> dict:
        """Fetch Open AI Response"""
        if not unmatch_data:
            return {}

        base_dict = {
            "sportsbook": unmatch_data.get("sportsbook"),
            "original_league": unmatch_data.get("original_league"),
            "received_name": unmatch_data.get("received_name"),
            "source": "OpenAI"
        }

        try:
            response = await self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "user", "content": extract_prompt(name=unmatch_data.get("received_name"), league=unmatch_data.get("original_league"))}
                ],
                timeout=120
            )
        # Continue to return empty dicts, as balance needs to be reloaded.
        except openai.RateLimitError as e:
            insert_log(
                book_name="OpenAI",
                error_type=ErrorTypes.BILLING,
                error_message="Reload OpenAI Balance"
            )
            return {}

        except Exception as e:
            return {
                **base_dict,
                "error_message": str(e)
            }

        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {
                **base_dict,
                "error_message": "Invalid JSON response"
            }

        return {
            **parsed,
            **base_dict
        }

    async def get_ai_response(self, non_matched_data: list, batch_size: int = 100):
        self.update_redis(redis_keys={row.get("redis_key") for row in non_matched_data})
        # Prevents duplicates from happening and wasting AI tokens.
        filtered_non_matched = self._check_verification_table(non_matched_data)

        if not filtered_non_matched:
            return

        ai_responses = []
        batches = list(batched(filtered_non_matched, batch_size))

        for n, batch in enumerate(batches, start=1):
            logger.info(f"Sending batch {n} of {len(batches)} ({len(batch)} teams) to AI")

            task = [self.fetch_response(row) for row in batch]
            response = await asyncio.gather(*task)

            if response:
                ai_responses.extend(response)

        self.update_verification_teams(ai_teams=ai_responses)
        self.update_redis(redis_keys=set(row.get("redis_key") for row in non_matched_data))


    async def handle_team_mapping(self, teams: list):
        if not teams:
            return

        with self.session_factory() as db_session:
            verified_teams = VerifiedTeams.get_mapping(db_session=db_session)
            normalized_names = set(verified.get("normalized_name").lower() for verified in verified_teams.values())

        modified_teams = [
            {
                "book": team.get("book"),
                "category": team.get("category"),
                "league": split_team[0],
                "name": split_team[1],
                "redis_key": f'teams:{team.get("name")}'
            }

            for team in teams
            if len(split_team := team.get("name").split("|", 1)) == 2
        ]

        actions = self.fuzzy_match(unmapped_data=modified_teams, mapped_keys=normalized_names, verified_teams=verified_teams)
        redis_keys = actions["redis_keys"]
        matched_teams = actions["matched"]
        unmatch_teams = actions["non_matched"]
        self.update_verified_teams(matched_teams=matched_teams)
        self.update_redis(redis_keys=redis_keys)
        await self.get_ai_response(non_matched_data=list(unmatch_teams.values()))

    async def controller(self):
        redis_keys = self.mapping_redis_manager.get_all_key_values()

        grouped_keys = defaultdict(list)
        for key in redis_keys:
            if key.get("category") in ["stats", "leagues"]:
                grouped_keys[key.get("category")].append({
                    "received_name": key.get("name"),
                    "sportsbook": key.get("book"),
                })
            else:
                grouped_keys[key.get("category")].append(key)

        grouped_keys = dict(grouped_keys)

        self.update_stats_verification(stats=grouped_keys.get("stats", []))
        self.update_league_verification(leagues=grouped_keys.get("leagues", []))
        await self.handle_team_mapping(teams=grouped_keys.get("teams", []))



if __name__ == "__main__":
    vm = VerificationMapping()
    asyncio.run(vm.controller())
