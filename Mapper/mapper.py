import asyncio
import os
from collections import defaultdict
from Mapper.database import Database
from rapidfuzz import fuzz, process
import textdistance
from concurrent.futures import ThreadPoolExecutor
from Mapper.ai_mapper import AIMapper

executor = ThreadPoolExecutor(max_workers=os.cpu_count())

ESPORT_LEAGUES = ["LOL", "CS2", "DOTA2", "VAL", "COD"]


class Mapper:
    def __init__(self):
        self.db = Database()

    def clean(self, s: str):
        return s.strip().replace('\xa0', '').replace('\u200b', '').lower()

    def group_teams_by_name(self, database_teams):
        normalized = defaultdict(list)
        received = defaultdict(list)
        for team in database_teams:
            normalized[self.clean(team[0])].append(team)
            received[self.clean(team[1])].append(team)
        return [normalized, received]

    def find_matches(self, args):
        """Compare names against database and compare common names against RapidFuzz"""
        team_data = args[0]
        database_teams = args[1]

        league_upper = team_data.get('league').upper()
        received_name = team_data.get('team_name').lower()
        sportsbook = team_data.get('sportsbook', None)
        SOURCE = "RapidFuzz"

        # Group teams by normalized and received names
        name_sources = self.group_teams_by_name(database_teams)

        for name_dict in name_sources:
            if received_name in name_dict:
                matched_teams = name_dict[received_name]
                for matched_team in matched_teams:

                    # Check if the league matches or base league.
                    base_league = matched_team[4].split(",") if matched_team[4] else []
                    if matched_team[3].upper() != league_upper and league_upper not in base_league:
                        continue

                    return {
                        "found": True,
                        "team_name": matched_team[0],
                        "league": matched_team[3].upper() if matched_team[3] and matched_team[
                            3] not in ESPORT_LEAGUES else league_upper,
                        "original_league": league_upper,
                        "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                        "original_name": received_name,
                        "update_db": False,
                        "source": SOURCE,
                        "sportsbook": sportsbook
                    }

        # Match against normalized and received names first
        for name_dict in name_sources:
            match = process.extractOne(received_name.lower(), name_dict.keys(), scorer=fuzz.ratio, score_cutoff=90)
            if match:
                matched_str, score, _ = match
                if 95 <= score <= 100:
                    matched_teams = name_dict[matched_str]
                    for matched_team in matched_teams:
                        base_league = matched_team[4].split(",") if matched_team[4] else []

                        # Check if the league matches or base league.
                        if matched_team[3].upper() != league_upper and league_upper not in base_league:
                            continue

                        return {
                            "found": True,
                            "team_name": matched_team[0],
                            "league": matched_team[3].upper() if matched_team[3] and matched_team[
                                3] not in ESPORT_LEAGUES else league_upper,
                            "original_league": league_upper,
                            "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                            "original_name": received_name,
                            "update_db": True,
                            "source": SOURCE,
                            "sportsbook": sportsbook
                        }

        other_model = self.textdistance_match(
            received_name=received_name,
            name_sources=name_sources,
            league_upper=league_upper,
            sportsbook=sportsbook,
        )

        if other_model.get("found"):
            return other_model

        return {
            "found": False,
            "team_name": received_name,
            "league": league_upper,
            "solo_game": team_data.get("solo_game"),
            "update_db": False,
            "source": SOURCE,
            "sportsbook": sportsbook
        }

    def textdistance_match(self, received_name, name_sources, league_upper, sportsbook):
        """Use textdistance library for matching using various algorithms"""
        SOURCE = "RapidFuzz"

        for name_dict in name_sources:
            for team_name in name_dict.keys():
                score = textdistance.cosine.similarity(received_name.lower(), team_name)
                if score > 0.95:
                    matched_teams = name_dict[team_name]
                    for matched_team in matched_teams:

                        # Check if the league matches or base league.
                        base_league = matched_team[4].split(",") if matched_team[4] else []

                        if matched_team[3].upper() != league_upper and league_upper not in base_league:
                            continue

                        return {
                            "found": True,
                            "team_name": matched_team[0],
                            "league": matched_team[3].upper() if matched_team[3] and matched_team[
                                3] not in ESPORT_LEAGUES else league_upper,
                            "original_league": league_upper,
                            "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                            "original_name": received_name,
                            "update_db": True,
                            "source": SOURCE,
                            "sportsbook": sportsbook
                        }

                score = textdistance.jaro_winkler.similarity(received_name.lower(), team_name)
                if score > 0.95:
                    matched_teams = name_dict[team_name]
                    for matched_team in matched_teams:

                        # Check if the league matches or base league.
                        base_league = matched_team[4].split(",") if matched_team[4] else []

                        if matched_team[3].upper() != league_upper and league_upper not in base_league:
                            continue

                        return {
                            "found": True,
                            "team_name": matched_team[0],
                            "league": matched_team[3].upper() if matched_team[3] and matched_team[
                                3] not in ESPORT_LEAGUES else league_upper,
                            "original_league": league_upper,
                            "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                            "original_name": received_name,
                            "update_db": True,
                            "source": SOURCE,
                            "sportsbook": sportsbook
                        }

        return {"found": False}


    async def controller(self, team_data):
        database_teams = await self.db.reload_teams()
        database_teams = [tuple(row) for row in database_teams]

        if not database_teams:
            return []

        args = [(data, database_teams) for data in team_data]

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
            await self.db.bulk_update_ai_table(teams_to_pass_to_ai)

        return teams_to_return











