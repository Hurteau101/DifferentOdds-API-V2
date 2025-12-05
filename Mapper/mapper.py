import asyncio
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from orjson import orjson
from Mapper.database import Database
from rapidfuzz import fuzz, process
from Redis.redis_manager import RedisSync

executor = ThreadPoolExecutor(max_workers=os.cpu_count())

class Mapper:
    def __init__(self):
        self.db = Database()
        self.redis = RedisSync(db=3)

    def clean(self, s: str):
        return s.strip().replace('\xa0', '').replace('\u200b', '').lower()

    def mapper_process_worker(self, find_fn, args_list):
        return [find_fn(arg) for arg in args_list]

    def group_teams_by_name(self, database_teams):
        """
        Produces:
        {
            "NBA": (normalized_dict, received_dict),
            "NFL": (normalized_dict, received_dict)
        }
        """
        league_map = defaultdict(lambda: [defaultdict(list), defaultdict(list)])

        for team in database_teams:
            # team = (team_name, received_name, abbr, league, base_leagues)
            league = (team[3] or "").upper()

            # Normalized = Verified Name from DB
            # Received = Name as received from Sportsbook
            normalized_dict, received_dict = league_map[league]
            normalized_dict[self.clean(team[0])].append(team)
            received_dict[self.clean(team[1])].append(team)

        return league_map


    def find_matches(self, args):
        """Compare names against database and compare common names against RapidFuzz"""
        team_data, league_index = args

        league_upper = team_data.get('league', '').upper()
        received_name_raw = team_data.get('team_name') or ''
        received_name = received_name_raw.lower()
        sportsbook = team_data.get("sportsbook")
        source = "RapidFuzz"

        redis_key = f"team_map:{league_upper}:{received_name}"
        redis_cached = self.redis.get(redis_key)

        if redis_cached:
            return orjson.loads(redis_cached)

        # Only grab leagues that match.
        name_sources = league_index.get(league_upper)
        if not name_sources:
            result = {
                "found": False,
                "team_name": received_name,
                "league": league_upper,
                "solo_game": team_data.get("solo_game"),
                "update_db": False,
                "source": source,
                "sportsbook": sportsbook
            }

            self.redis.set(redis_key, orjson.dumps(result), ex=86400)
            return result

        normalized_dict, received_dict = name_sources
        name_dicts = (normalized_dict, received_dict)

        # Exact Match Check
        for name_dict in name_dicts:
            if received_name in name_dict:
                matched_team = name_dict[received_name][0]

                result = {
                    "found": True,
                    "team_name": matched_team[0],
                    "league": matched_team[3].upper(),
                    "original_league": league_upper,
                    "abbreviation": matched_team[2],
                    "original_name": received_name,
                    "update_db": False,
                    "source": source,
                    "sportsbook": sportsbook,
                }

                self.redis.set(redis_key, orjson.dumps(result), ex=86400)
                return result


        # Fuzzy Matching (Strict)
        for name_dict in name_dicts:
            if not name_dict:
                continue


            match = process.extractOne(
                received_name,
                name_dict.keys(),
                scorer=fuzz.ratio,
                score_cutoff=95,
            )

            if match:
                matched_str, score, _ = match

                if 95 <= score <= 100:
                    matched_team = name_dict[matched_str][0]

                    result = {
                        "found": True,
                        "team_name": matched_team[0],
                        "league": matched_team[3].upper(),
                        "original_league": league_upper,
                        "abbreviation": matched_team[2],
                        "original_name": received_name,
                        "update_db": True,
                        "source": source,
                        "sportsbook": sportsbook,
                    }

                    self.redis.set(redis_key, orjson.dumps(result), ex=86400)
                    return result

        # No Match Found
        result = {
            "found": False,
            "team_name": received_name,
            "league": league_upper,
            "solo_game": team_data.get("solo_game"),
            "update_db": False,
            "source": source,
            "sportsbook": sportsbook,
        }

        self.redis.set(redis_key, orjson.dumps(result), ex=86400)
        return result


    async def controller(self, team_data):
        database_teams = await self.db.reload_teams()
        database_teams = [tuple(row) for row in database_teams]

        if not database_teams:
            return []

        league_index = self.group_teams_by_name(database_teams)

        args = [(data, league_index) for data in team_data]

        loop = asyncio.get_running_loop()

        results = await loop.run_in_executor(
            executor,
            lambda: list(executor.map(self.find_matches, args))
        )

        teams_to_return = [result for result in results if result.get("found")] # Return these teams for mapping.
        teams_to_update  = [team for team in teams_to_return if team.get("update_db")] # Update DB with these teams.

        # # Bulk update the database with any 'close' RapidFuzz matches.
        if teams_to_update :
            await self.db.bulk_update_verification_table(teams_to_update)


        existing_verification_data = await self.db.get_verification_league_map()

        teams_to_pass_to_ai = []
        for result in results:
            if not result or result["found"]:
                continue

            name = result["team_name"].lower()
            league = result["league"].upper()
            orig = (result.get("original_league") or result["league"]).upper()

            if name not in existing_verification_data:
                teams_to_pass_to_ai.append(result)
                continue

            leagues_seen = existing_verification_data[name]

            if league in leagues_seen or orig in leagues_seen:
                continue

            teams_to_pass_to_ai.append(result)

        if teams_to_pass_to_ai:
            # await self.redis.bulk_store_data(teams_to_pass_to_ai)
            # print(teams_to_pass_to_ai)
            await self.db.bulk_update_ai_table(teams_to_pass_to_ai)

        return teams_to_return
