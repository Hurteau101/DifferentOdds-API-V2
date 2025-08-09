import asyncio
import json
import multiprocessing
from concurrent.futures.process import ProcessPoolExecutor
import textdistance
from Settings.logger import FileLogger
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from Mapper.database import Database
from openai import AsyncOpenAI
import os

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

COMMON_LEAGUES = [
    "NHL",
    "NFL",
    "CFL",
    "CBB",
    "CFB"
    "NBA",
    "WNBA",
    "MLB",
]


def find_matches(args):
    """Compare names against database and compare common names against RapidFuzz"""
    team_data = args[0]
    database_teams = args[1]

    league_upper = team_data.get('league').upper()
    received_name = team_data.get('team_name').lower()


    name_sources = [
        {team[0].lower(): team for team in database_teams},  # Normalized names
        {team[1].lower(): team for team in database_teams},  # Received names
    ]

    # Check for exact match first.
    for name_dict in name_sources:
        if received_name in name_dict:
            matched_team = name_dict[received_name]

            # This check is to ensure if it's a common league and if it is, ensure that the league matches.
            if matched_team[3].upper() in COMMON_LEAGUES and matched_team[3].upper() != league_upper:
                continue

            return {
                "found": True,
                "team_name": matched_team[0],
                "league": matched_team[3].upper() if matched_team[3] else league_upper,
                "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                "original_name": received_name,
                "update_db": False,
            }

    # Match against normalized and received names first
    for name_dict in name_sources:
        match = process.extractOne(received_name.lower(), name_dict.keys(), scorer=fuzz.ratio, score_cutoff=95)
        if match:
            matched_str, score, _ = match
            if 95 <= score < 100:
                matched_team = name_dict[matched_str]

                # This check is to ensure if it's a common league and if it is, ensure that the league matches.
                if matched_team[3].upper() in COMMON_LEAGUES and matched_team[3].upper() != league_upper:
                    continue

                return {
                    "found": True,
                    "team_name": matched_team[0],
                    "league": matched_team[3].upper() if matched_team[3] else league_upper,
                    "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                    "original_name": received_name,
                    "update_db": True
                }


    other_model = textdistance_match(
        received_name=received_name,
        name_sources=name_sources,
        league_upper=league_upper
    )

    if other_model.get("found"):
        return other_model

    return {
        "found": False,
        "team_name": received_name,
        "league": league_upper,
        "solo_game": team_data.get("solo_game"),
        "update_db": False,
    }


def textdistance_match(received_name, name_sources, league_upper):
    """Use textdistance library for matching using various algorithms"""
    for name_dict in name_sources:
        for team_name in name_dict.keys():
            score = textdistance.cosine.similarity(received_name.lower(), team_name)
            if score > 0.90:
                matched_team = name_dict[team_name]

                # This check is to ensure if it's a common league and if it is, ensure that the league matches.
                if matched_team[3].upper() in COMMON_LEAGUES and matched_team[3].upper() != league_upper:
                    continue

                return {
                    "found": True,
                    "team_name": matched_team[0],
                    "league": matched_team[3].upper() if matched_team[3] else league_upper,
                    "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                    "original_name": received_name,
                    "update_db": True
                }

            score = textdistance.jaro_winkler.similarity(received_name.lower(), team_name)
            if score > 0.90:
                matched_team = name_dict[team_name]

                # This check is to ensure if it's a common league and if it is, ensure that the league matches.
                if matched_team[3].upper() in COMMON_LEAGUES and matched_team[3].upper() != league_upper:
                    continue

                return {
                    "found": True,
                    "team_name": matched_team[0],
                    "league": matched_team[3].upper() if matched_team[3] else league_upper,
                    "abbreviation": matched_team[2].upper() if matched_team[2] else None,
                    "original_name": received_name,
                    "update_db": True
                }

    return {"found": False}



class Mapper:
    def __init__(self):
        load_dotenv(dotenv_path=env_path)
        self.db = Database()
        self.database_teams = self.db.load_teams()
        self.client = AsyncOpenAI(api_key=os.getenv("OPEN_AI_KEY"))
        self.file_logger = FileLogger()
        self.file_logger.set_log_file("OpenAI.log")


    async def controller(self, team_data):
        database_teams = self.database_teams

        # Run in parallel to find all exact or close matches using RapidFuzz
        args = [(data, database_teams) for data in team_data]
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            results = await loop.run_in_executor(
                None,
                lambda: list(executor.map(find_matches, args))
            )


        teams_to_return = [result for result in results if result.get("found")] # Return these teams for mapping.
        database_teams = [team for team in teams_to_return if team.get("update_db")] # Update DB with these teams.

        # Any teams unable to match will be passed to OpenAI to try to map.
        teams_to_pass_to_ai = [
            result for result in results
            if result and not result.get("found") and any(result.values())
        ]

        # Bulk update the database with any 'close' RapidFuzz matches.
        if database_teams:
            self.db.bulk_update_mapper_table(teams_to_return)

        if teams_to_pass_to_ai:
            print(f"Passing {len(teams_to_pass_to_ai)} to AI")
            team = await self.run_open_ai(teams_to_pass_to_ai)
            if team:
                teams_to_return.extend(team)

        # List of teams to return to map back to the original data.
        return teams_to_return

    async def fetch_response(self, prompt, prompt_data):
        from Settings.dfs_book_base import DFSBookBase

        # Load not found data to ensure non-matching calls aren't called repeatedly.
        not_found = self.db.load_not_found()
        key = (prompt_data.get("team_name").lower(), prompt_data.get("league").upper())

        if key in not_found:
            return None

        print(f"Running AI {key}")

        #### THESE ARE WAY MORE EXPENSIVE SO COMMENTED OUT TO TEST OTHER MODELS.

        # response = await self.client.responses.create(
        #     # model="gpt-4.1",
        #     model="gpt-5-nano",
        #     tools=[{"type": "web_search_preview"}],
        #     input=prompt
        # )

        # response = await self.client.responses.create(
        #     model="gpt-3.5-turbo",
        #     input=prompt
        # )

        # content = response.output_text

        response = await self.client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        if content is None or any(x in content for x in ["NULL", "null"]):
            self.db.insert_not_found(team_name=prompt_data.get("team_name").lower(),
                                     league=prompt_data.get("league").upper())
            return None

        try:
            normalized_data = json.loads(content)
            if prompt_data.get("solo_game"):
                # If any are blank, most likely AI couldn't find the mapping, so we store in not found DB.
                if normalized_data is None or normalized_data.get("full_name") is None or normalized_data.get("league") is None:
                    self.db.insert_not_found(team_name=prompt_data.get("team_name").lower(),
                                             league=prompt_data.get("league").upper())
                    return None
            else:
                if normalized_data is None or normalized_data.get("full_name") is None or normalized_data.get("abbreviation") is None:
                    self.db.insert_not_found(team_name=prompt_data.get("team_name").lower(),
                                             league=prompt_data.get("league").upper())
                    return None

            mapped_data = {
                "found": True,
                "team_name": DFSBookBase.clean_and_normalize_name(normalized_data.get("full_name")),
                "league": normalized_data.get("league", prompt_data.get('league').upper()),
                "abbreviation": normalized_data.get("abbreviation"),
                "original_name": prompt_data.get("team_name")

            }

            # Update the database with the OpenAI matches.
            self.db.update_mapper_table(
                normalized_name=mapped_data.get("team_name"),
                received_name=prompt_data.get("team_name").lower(),
                abbreviation=mapped_data.get("abbreviation").upper() if mapped_data.get("abbreviation") else None,
                league=mapped_data.get("league").upper()
            )

            return mapped_data

        except json.JSONDecodeError:
            self.file_logger.log(
                message=f"Could not parse JSON: {content}",
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

        results = await asyncio.gather(*tasks)
        results = [result for result in results if result and any(result.values())]
        return results

    def _extract_prompt(self, prompt):
        # Open AI prompts. Using different prompts based on a solo or team game.
        if prompt.get("solo_game"):
            return (
                "Normalize this solo player name to their official first and last name ONLY no middle name and the exact league they play in.  Limit to 1 web source"
                f"Player name: {prompt.get('team_name')}, League: {prompt.get('league')}. "
                "The 'league' should be a specific organization like 'ATP', 'WTA', 'UFC', 'PGA', 'MLS', or anything like that etc. Do not use generic names like 'TENNIS', 'MMA', 'FIFA' or anything like that unless its an unknown league"
                "If you cannot find the league or player return NULL. "
                "Return your answer ONLY as a JSON object with keys 'full_name' which is there first and last name and 'league'. "
                "Do not wrap the json codes in JSON markers"
            )

        return (
                f"Normalize this team name to its official sports team name and abbreviation, based on the league.  Limit to 1 web source"
                f"Do NOT include terms like 'University', 'College', or other institution names unless they are officially part of the team name. "
                f"Ensure you include there full name though like Boston Celtics, etc. "
                f"Focus on how the team is referred to in sports stats, broadcasts, or standings. "
                "The 'league' should be a specific organization like 'NFL', 'CFB', 'NHL', 'CBB', or anything like that etc. Do not use generic names like 'BASKETBALL', 'HOCKEY', 'SOCCER' or anything like that unless its an unknown league"
                f"Team name: {prompt.get('team_name')}, League: {prompt.get('league')}. "
                f"Return your answer ONLY as a JSON object with keys 'full_name' and 'abbreviation'. "
                f"Do not wrap the JSON in code blocks or markdown."
            )




