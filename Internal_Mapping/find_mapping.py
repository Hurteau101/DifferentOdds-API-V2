import asyncio
from collections import defaultdict
from rapidfuzz import fuzz, process
from Database.database_old import Database
from Redis.redis_manager import RedisAsyncManager
from Utils.helpers import clean_structure

# TODO:
#### RENAME FILE

#### IF USING THIS FILE - CHANGE REDIS DB

class FindMapper:
    def __init__(self):
        self.db = Database()
        self.redis = RedisAsyncManager(database=3)

    def group_teams_by_name(self, database_teams: list) -> dict:
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
            normalized_dict[clean_structure(team[0])].append(team)
            received_dict[clean_structure(team[1])].append(team)

        return league_map

    async def find_matches(self, args: tuple) -> dict:
        """Compare names against database and compare common names against RapidFuzz"""
        team_data, league_index = args
        league_upper = team_data.get('league', '').upper()

        received_name_raw = team_data.get('team_name') or ''
        received_name = received_name_raw.lower()
        sportsbook = team_data.get("sportsbook")
        source = "RapidFuzz"

        # if received_name == "jan choinski":
        #     league_upper = "ATP"
        #     test = league_index.values()
        #     for name in test:
        #         for name_dict in name:
        #             print(name_dict.keys())

        redis_key = f"team_map:{league_upper}:{received_name}"

        # Only grab leagues that match unless its a solo game.
        if not team_data.get("solo_game"):
            name_sources = league_index.get(league_upper)

        else:
            name_sources = next(
                (
                    pair
                    for pair in league_index.values()
                    for name_dict in pair
                    if received_name in name_dict
                ),
                None,
            )

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
            await self.redis.store_data(
                key_name=redis_key,
                data_to_store=result,
                key_expiration=86400  # 24 Hours
            )

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
                    "solo_game": team_data.get("solo_game"),
                    "original_league": league_upper,
                    "abbreviation": matched_team[2],
                    "original_name": received_name,
                    "update_db": False,
                    "source": source,
                    "sportsbook": sportsbook,
                }

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
                        "solo_game": team_data.get("solo_game"),
                        "original_league": league_upper,
                        "abbreviation": matched_team[2],
                        "original_name": received_name,
                        "update_db": True,
                        "source": source,
                        "sportsbook": sportsbook,
                    }

                    return result

        cached_miss = await self.redis.get_data(redis_key)
        if cached_miss:
            return cached_miss

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

        await self.redis.store_data(
            key_name=redis_key,
            data_to_store=result,
            key_expiration=86400  # 24 Hours
        )

        return result

    async def controller(self, team_data: list) -> list:
        database_teams = self.db.reload_teams()
        database_teams = [tuple(row) for row in database_teams]

        if not database_teams:
            return []

        league_index = self.group_teams_by_name(database_teams)

        args = [(data, league_index) for data in team_data]

        results = await asyncio.gather(
            *(self.find_matches(arg) for arg in args)
        )

        teams_to_return = [result for result in results if result.get("found")] # Return these teams for mapping.
        teams_to_update = [team for team in teams_to_return if team.get("update_db")] # Update DB with these teams.


        # # Bulk update the database with any 'close' RapidFuzz matches.
        if teams_to_update :
            self.db.bulk_update_verification_table(teams_to_update)


        existing_verification_data = self.db.get_verification_league_map()

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
            self.db.bulk_update_ai_table(teams_to_pass_to_ai)

        return teams_to_return
