import asyncio
import aiohttp
from Utils.helpers import clean_and_normalize
from Utils.request_caller import APICaller
from curl_cffi import AsyncSession as CurlAsyncSession

class MLBStats(APICaller):
    def __init__(self, session: CurlAsyncSession):
        super().__init__()
        self.session = session

    async def _get_teams(self):
        teams = await self.api_caller(
            session=self.session,
            url=f"https://statsapi.mlb.com/api/v1/teams?sportId=1&activeStatus=Y&fields=teams,id,name",
            method="GET",
        )

        # API only has the name 'Athletics', whereas Bettorodds uses 'Oakland Athletics', so we need to adjust the name here to ensure the mapping works correctly
        for team in teams.get("teams", []):
            if "athletics" in team.get("name").lower():
                team["name"] = "Oakland Athletics"

        return {
            team.get("id"): team.get("name")
            for team in teams.get("teams", [])
        }


    async def _get_players(self, team_ids: list):
        tasks = [
            self.api_caller(
                session=self.session,
                url=f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active&fields=roster,person,fullName",
                method="GET",
            )
            for team_id in team_ids
        ]

        results = await asyncio.gather(*tasks)

        player_mapping = {}

        for team_id, players in zip(team_ids, results):
            player_mapping.setdefault(team_id, []).extend([
                clean_and_normalize(player.get("person", {}).get("fullName"))
                for player in players.get("roster", [])
            ])

        return player_mapping




    async def run_mapping(self):
        teams = await self._get_teams()
        players = await self._get_players(team_ids=list(teams.keys()))
        combined = {
            team_name: {
                "team_id": team_id,
                "players": players.get(team_id, [])
            }
            for team_id, team_name in teams.items()
        }

        return combined

if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            mlb = MLBStats(session=session)
            await mlb.run_mapping()

    asyncio.run(main())
