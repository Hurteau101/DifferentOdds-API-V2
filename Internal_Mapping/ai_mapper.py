import asyncio
import json
import os
from Database.database import Database
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError
from Utils.helpers import clean_structure

class AIMapper:
    def __init__(self):
        load_dotenv()
        self.client = AsyncOpenAI(api_key=os.getenv("OPEN_AI_KEY"))
        self.db = Database()
        self.semaphore = asyncio.Semaphore(5)

    async def run_open_ai(self):
        existing_map = self.db.get_verification_league_map()
        ai_teams = self.db.get_ai_teams()


        teams_for_ai = []

        for row in ai_teams:
            name = row["team_name"].lower()
            league = row["league"].upper()

            if name not in existing_map:
                teams_for_ai.append(row)
                continue

            seen = existing_map[name]

            if league in seen:
                continue

            teams_for_ai.append(row)

        BATCH_SIZE = 100

        team_ai_counter = len(teams_for_ai)

        for i in range(0, len(teams_for_ai), BATCH_SIZE):
            batch = teams_for_ai[i:i + BATCH_SIZE]

            print(f"\n--- Starting batch {i // BATCH_SIZE + 1}  ({len(batch)} items) / {team_ai_counter} Teams ---\n")
            team_ai_counter = team_ai_counter - BATCH_SIZE

            tasks = [
                self.fetch_response(
                    prompt=self._extract_prompt(row),
                    prompt_data=row
                )
                for row in batch
            ]

            try:
                await asyncio.gather(*tasks)
                processed_pairs = {
                    (row["team_name"].lower(), row["league"].upper())
                    for row in teams_for_ai
                }

                self.db.delete_ai_rows(processed_pairs)

            except OpenAIError as e:
                print(e)
                # Sentry will handle logging.
                continue
            except Exception as e:
                print(e)

    async def fetch_response(self, prompt: str, prompt_data: dict) -> dict | None:
        print(f"Running AI {prompt_data.get('team_name')} | {prompt_data.get('league')}")

        response = await self.client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "user", "content": prompt}
            ],
            timeout=120
        )

        content = response.choices[0].message.content

        # Check if the content is None or contains "NULL" or "null" we add to verification table, avoiding any further processing.
        if content is None or any(x in content for x in ["NULL", "null"]):
            self.db.update_verification_table(
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
                    self.db.update_verification_table(
                        received_name=prompt_data.get("team_name").lower(),
                        league=prompt_data.get("league").upper(),
                        original_league=prompt_data.get("league").upper(),
                        sportsbook=prompt_data.get("sportsbook", "unknown"),
                        source="OpenAI",
                    )

                    return None
            else:
                if normalized_data is None or normalized_data.get("full_name") is None or normalized_data.get("abbreviation") is None:
                    self.db.update_verification_table(
                        received_name=prompt_data.get("team_name").lower(),
                        league=prompt_data.get("league").upper(),
                        original_league=prompt_data.get("league").upper(),
                        sportsbook=prompt_data.get("sportsbook", "unknown"),
                        source="OpenAI",
                    )
                    return None

            try:
                mapped_data = {
                    "found": True,
                    "team_name": clean_structure(normalized_data.get("full_name")),
                    "league": normalized_data.get("league", prompt_data.get('league').upper()),
                    "original_league": prompt_data.get('league').upper(),
                    "abbreviation": normalized_data.get("abbreviation"),
                    "original_name": prompt_data.get("team_name")

                }

                # Update the database with the OpenAI matches.
                self.db.update_verification_table(
                    normalized_name=mapped_data.get("team_name"),
                    received_name=prompt_data.get("team_name").lower(),
                    abbreviation=mapped_data.get("abbreviation").upper() if mapped_data.get("abbreviation") else None,
                    league=mapped_data.get("league").upper(),
                    original_league=prompt_data.get("league").upper(),
                    sportsbook=prompt_data.get("sportsbook", "unknown"),
                    source="OpenAI",
                )

                return mapped_data
            except Exception as e:
                print(f"Error updating verification table: {e}")

        except json.JSONDecodeError:
            # Sentry will handle logging.
            return None


    def _extract_prompt(self, prompt: dict) -> str:
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

if __name__ == "__main__":
    ai_mapper = AIMapper()
    asyncio.run(ai_mapper.run_open_ai())