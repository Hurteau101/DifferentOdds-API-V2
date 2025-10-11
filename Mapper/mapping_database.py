import asyncio
import inspect
import json
import multiprocessing
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
import textdistance
from Settings.logger import FileLogger
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from Mapper.database import Database
from openai import AsyncOpenAI, OpenAIError
import os
from collections import defaultdict

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

ESPORT_LEAGUES = ["LOL", "CS2", "DOTA2", "VAL", "COD"]

def group_teams_by_name(database_teams):
    normalized = defaultdict(list)
    received = defaultdict(list)
    for team in database_teams:
        normalized[team[0].lower()].append(team)
        received[team[1].lower()].append(team)
    return [normalized, received]


def find_matches(args):
    """Compare names against database and compare common names against RapidFuzz"""
    team_data = args[0]
    database_teams = args[1]

    league_upper = team_data.get('league').upper()
    received_name = team_data.get('team_name').lower()
    sportsbook = team_data.get('sportsbook', None)
    SOURCE = "RapidFuzz"

    # Group teams by normalized and received names
    name_sources = group_teams_by_name(database_teams)

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
                    "league": matched_team[3].upper() if matched_team[3] and matched_team[3] not in ESPORT_LEAGUES else league_upper,
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
                        "league": matched_team[3].upper() if matched_team[3] and matched_team[3] not in ESPORT_LEAGUES else league_upper,
                        "original_league": league_upper,
                        "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                        "original_name": received_name,
                        "update_db": True,
                        "source": SOURCE,
                        "sportsbook": sportsbook
                    }


    other_model = textdistance_match(
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


def textdistance_match(received_name, name_sources, league_upper, sportsbook):
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
                        "league": matched_team[3].upper() if matched_team[3] and matched_team[3] not in ESPORT_LEAGUES else league_upper,
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
                        "league": matched_team[3].upper() if matched_team[3] and matched_team[3] not in ESPORT_LEAGUES else league_upper,
                        "original_league": league_upper,
                        "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                        "original_name": received_name,
                        "update_db": True,
                        "source": SOURCE,
                        "sportsbook": sportsbook
                    }

    return {"found": False}


class Mapper:
    def __init__(self):
        load_dotenv(dotenv_path=env_path)
        self.db = Database()
        # self.database_teams = self.db.load_teams()
        self.client = AsyncOpenAI(api_key=os.getenv("OPEN_AI_KEY"))
        self.file_logger = FileLogger()

        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_folder = os.path.join(current_dir, "Open AI Logs")

        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        log_path = os.path.join(log_folder, "OpenAI.log")

        self.file_logger.set_log_file(log_path)
        caller_file_full = inspect.stack()[2].filename  # Path of the caller.
        self.caller_file_name = os.path.basename(caller_file_full) # File name of the caller


    async def controller(self, team_data):
        database_teams = await self.db.load_teams()

        # database_teams = self.database_teams

        # Run in parallel to find all exact or close matches using RapidFuzz
        args = [(data, database_teams) for data in team_data]
        loop = asyncio.get_running_loop()
        # with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        #     results = await loop.run_in_executor(
        #         None,
        #         lambda: list(executor.map(find_matches, args))
        #     )

        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            results = await loop.run_in_executor(
                None,
                lambda: list(executor.map(find_matches, args))
            )


        teams_to_return = [result for result in results if result.get("found")] # Return these teams for mapping.
        database_teams = [team for team in teams_to_return if team.get("update_db")] # Update DB with these teams.

        # # Bulk update the database with any 'close' RapidFuzz matches.
        if database_teams:
            await self.db.bulk_update_verification_table(database_teams)

        existing_names = await self.db.get_all_received_names()

        # # Any teams unable to match will be passed to OpenAI to try to map.
        # teams_to_pass_to_ai = [
        #     result for result in results
        #     if result
        #        and not result.get("found")
        #        and any(result.values())
        #        and f"{result.get('team_name').lower()}-{result.get('league').lower()}" not in existing_names
        # ]

        teams_to_pass_to_ai = [
            result for result in results
            if result
               and not result.get("found")
               and any(result.values())
               and result.get('team_name').lower() not in existing_names
        ]
        #
        # print(existing_names)
        #
        if teams_to_pass_to_ai:
            print(f"Passing {len(teams_to_pass_to_ai)} to AI")
            team = await self.run_open_ai(teams_to_pass_to_ai)
            if team:
                teams_to_return.extend(team)

        # List of teams to return to map back to the original data.
        return teams_to_return

    async def fetch_response(self, prompt, prompt_data):
        from Settings.dfs_book_base import DFSBookBase

        print(f"Running AI {prompt_data.get('team_name')} | {prompt_data.get('league')}")

        #### THESE ARE WAY MORE EXPENSIVE SO COMMENTED OUT TO TEST OTHER MODELS.

        # response = await self.client.responses.create(
        #     # model="gpt-4.1",
        #     model="gpt-5-nano",
        #     tools=[{"type": "web_search_preview"}],
        #     input=prompt
        # )
        #
        # response = await self.client.responses.create(
        #     model="gpt-3.5-turbo",
        #     input=prompt
        # )
        #
        # content = response.output_text

        ##############################################

        response = await self.client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        # Check if the content is None or contains "NULL" or "null" we add to verification table, avoiding any further processing.
        if content is None or any(x in content for x in ["NULL", "null"]):
            await self.db.update_verification_table(
                received_name=prompt_data.get("team_name").lower(),
                league=prompt_data.get("league").upper(),
                original_league=prompt_data.get("league").upper(),
                sportsbook= prompt_data.get("sportsbook", "unknown"),
                source="OpenAI",
            )
            return None

        try:
            normalized_data = json.loads(content)
            if prompt_data.get("solo_game"):
                # If any are blank, most likely AI couldn't find the mapping, so we store in not found DB.
                if normalized_data is None or normalized_data.get("full_name") is None or normalized_data.get("league") is None:
                    await self.db.update_verification_table(
                        received_name=prompt_data.get("team_name").lower(),
                        league=prompt_data.get("league").upper(),
                        original_league=prompt_data.get("league").upper(),
                        sportsbook=prompt_data.get("sportsbook", "unknown"),
                        source="OpenAI",
                    )

                    return None
            else:
                if normalized_data is None or normalized_data.get("full_name") is None or normalized_data.get("abbreviation") is None:
                    await self.db.update_verification_table(
                        received_name=prompt_data.get("team_name").lower(),
                        league=prompt_data.get("league").upper(),
                        original_league=prompt_data.get("league").upper(),
                        sportsbook=prompt_data.get("sportsbook", "unknown"),
                        source="OpenAI",
                    )
                    return None

            mapped_data = {
                "found": True,
                "team_name": DFSBookBase.clean_and_normalize_name(normalized_data.get("full_name")),
                "league": normalized_data.get("league", prompt_data.get('league').upper()),
                "original_league": prompt_data.get('league').upper(),
                "abbreviation": normalized_data.get("abbreviation"),
                "original_name": prompt_data.get("team_name")

            }

            # Update the database with the OpenAI matches.
            await self.db.update_verification_table(
                normalized_name=mapped_data.get("team_name"),
                received_name=prompt_data.get("team_name").lower(),
                abbreviation=mapped_data.get("abbreviation").upper() if mapped_data.get("abbreviation") else None,
                league=mapped_data.get("league").upper(),
                original_league=prompt_data.get("league").upper(),
                sportsbook=prompt_data.get("sportsbook", "unknown"),
                source="OpenAI",
            )

            return mapped_data

        except json.JSONDecodeError:
            self.file_logger.log(
                message=f"Could not parse JSON: {content}",
                file=self.caller_file_name,
                level="INFO"
            )

            return None



    async def run_open_ai(self, prompt_data):
        # Run this Async, to speed up the process.
        tasks = [
            self.fetch_response(
                prompt=self._extract_prompt(prompt),
                prompt_data=prompt
            )
            for prompt in prompt_data
        ]

        try:
            results = await asyncio.gather(*tasks)
            results = [result for result in results if result and any(result.values())]
            return results

        except OpenAIError as e:
            self.file_logger.log(
                message=f"{e}",
                file=self.caller_file_name,
                level="ERROR"
            )


    def _extract_prompt(self, prompt):
        # Open AI prompts. Using different prompts based on a solo or team game.
        if "/" in prompt.get("team_name"):
            if prompt.get("solo_game"):
                return (
                    "Normalize the 2 players between the '/' to there official first and last name ONLY no middle name and the exact league they play in."
                    f"Player names: {prompt.get('team_name')}, League: {prompt.get('league')}. "
                    "The 'league' should be a specific organization like 'ATP', 'WTA', 'UFC', 'PGA', 'MLS', or anything like that etc. Do not use generic names like 'TENNIS', 'MMA', 'FIFA' or anything like that unless its an unknown league"
                    "If you cannot find the league or EITHER player return NULL. "
                    "Please ensure you have the '/' dividing the 2 players in 'full_name'"
                    "Return your answer ONLY as a JSON object with keys 'full_name' which is both players first and last name and 'league'. "
                    "Do not wrap the json codes in JSON markers"
                )
            else:
                return (
                    "Normalize the 2 teams between the '/' to there official sports team name and abbreviation, based on the correct league. "
                    "Do NOT include terms like 'University', 'College', or other institution names unless they are officially part of the team names. "
                    "Ensure you include the full official team names, such as 'Boston Celtics' or 'Manchester United'. "
                    "The 'league' must be the specific competition or organization the team plays in (e.g., 'NFL', 'CFB', 'NHL', 'CBB', 'EPL', 'La Liga', 'MLS', 'UEFA CL', 'Serie A'). "
                    "Do NOT use generic names like 'BASKETBALL', 'HOCKEY', 'SOCCER', or 'FIFA'. "
                    "If the specific league cannot be confidently determined, return NULL for the league or EITHER team cannot be found, return NULL for 'full_name'"
                    "Please ensure you have the '/' dividing the 2 teams in 'full_name'"
                    f"Team name: {prompt.get('team_name')}, League: {prompt.get('league')}. "
                    "Return your answer ONLY as a JSON object with keys 'full_name', 'abbreviation', and 'league'. "
                    "Do not wrap the JSON in code blocks or markdown."
                )

        if prompt.get("solo_game"):
            return (
                "Normalize this solo player name to their official first and last name ONLY no middle name and the exact league they play in."
                f"Player name: {prompt.get('team_name')}, League: {prompt.get('league')}. "
                "The 'league' should be a specific organization like 'ATP', 'WTA', 'UFC', 'PGA', 'MLS', or anything like that etc. Do not use generic names like 'TENNIS', 'MMA', 'FIFA' or anything like that unless its an unknown league"
                "If you cannot find the league or player return NULL. "
                "Return your answer ONLY as a JSON object with keys 'full_name' which is there first and last name and 'league'. "
                "Do not wrap the json codes in JSON markers"
            )


        return (
            "Normalize this team name to its official sports team name and abbreviation, based on the correct league. "
            "Limit to 1 web source. "
            "Do NOT include terms like 'University', 'College', or other institution names unless they are officially part of the team name. "
            "Ensure you include the full official team name, such as 'Boston Celtics' or 'Manchester United'. "
            "The 'league' must be the specific competition or organization the team plays in (e.g., 'NFL', 'CFB', 'NHL', 'CBB', 'EPL', 'La Liga', 'MLS', 'UEFA CL', 'Serie A'). "
            "Do NOT use generic names like 'BASKETBALL', 'HOCKEY', 'SOCCER', or 'FIFA'. "
            "If the specific league cannot be confidently determined, return NULL for the league. "
            "For soccer teams, identify the exact league or competition (e.g., 'EPL', 'La Liga', 'MLS', 'Bundesliga', 'UEFA CL', 'Serie A') based on the team name. "
            "If there is a '/' in the 'team_name' then DO NOT change the team_name, just find the league they are in."
            f"Team name: {prompt.get('team_name')}, League: {prompt.get('league')}. "
            "Return your answer ONLY as a JSON object with keys 'full_name', 'abbreviation', and 'league'. "
            "Do not wrap the JSON in code blocks or markdown."
            )




