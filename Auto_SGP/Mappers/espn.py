import asyncio
from typing import Callable, Awaitable
import aiohttp

class ESPN:
    VALID_KEYS = ["sport", "espn_league"]

    def __init__(self, filter_data: dict):
        self.filters = filter_data

        if not self.filters:
            raise ValueError("League information is required to fetch teams.")

        if not isinstance(self.filters, dict):
            raise TypeError("League information must be a dictionary.")

        if not set(ESPN.VALID_KEYS).issubset(self.filters.keys()):
            raise KeyError(f"League information must contain the following keys: {ESPN.VALID_KEYS}")

    async def get_teams(self, session: aiohttp.ClientSession, api_caller: Callable[..., Awaitable[dict]]) -> dict:
        """
        Teams mapping function to get ESPN team IDs.
        :param session: An aiohttp ClientSession object
        :param api_caller: The API caller function to use for making requests
        :return: Returns a dictionary of team names to ESPN IDs
        """
        raw_teams = await api_caller(
            book_name="ESPNMapper",
            session=session,
            url=f"https://site.api.espn.com/apis/site/v2/sports/{self.filters['sport']}/{self.filters['espn_league']}/teams?limit=5000",
            method="GET",
        )

        return {
            teams.get("team", {}).get("displayName"): teams.get("team", {}).get("id")
            for data in raw_teams.get("sports")
            for league in data.get("leagues")
            for teams in league.get("teams")
        }

    async def runner(self, session: aiohttp.ClientSession, api_caller: Callable[..., Awaitable[dict]]) -> dict:
        """
        Main runner function to get player to team mapping.
        :param session: An aiohttp ClientSession object
        :param api_caller: The API caller function to use for making requests
        :return: Returns the player to team mapping as a dictionary
        """
        teams = await self.get_teams(session=session, api_caller=api_caller)
        tasks = [
            api_caller(
                book_name="ESPNMapper",
                session=session,
                url=f"https://site.api.espn.com/apis/site/v2/sports/{self.filters['sport']}/{self.filters['espn_league']}/teams/{team_id}/roster?limit=5000",
                method="GET",
            )
            for team_id in teams.values()
        ]

        results = await asyncio.gather(*tasks)

        return {
            player.get("displayName"): result.get("team", {}).get("displayName")
            for result in results
            for athlete in result.get("athletes", [])
            for player in (athlete.get("items") or [athlete])
            if player.get("displayName")
        }

