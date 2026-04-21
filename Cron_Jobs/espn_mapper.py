import asyncio
import re
from datetime import datetime, timezone
from itertools import chain
import aiohttp
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import APICaller, SportbookRequestType


class ESPNMapper(APICaller):
    ESPN_LEAGUES = [
        {"espn_league": "nba", "sport": "basketball"},
        {"espn_league": "nhl", "sport": "hockey"},
        {"espn_league": "mlb", "sport": "baseball"},
        {"espn_league": "nfl", "sport": "football"},
    ]

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(SportbookRequestType.ASYNC)
        self.session = session

    async def run_mapping(self):
        leagues, results = await self._get_teams()

        redis_instance = RedisAsyncManager(database=8)

        mapping = {}

        for index, league in enumerate(leagues):
            league_name = league.get("abbreviation")

            teams = {
                team.get("team", {}).get("displayName"): team.get("team", {}).get("id")
                for team in league.get("teams", [])
            }

            sport = results[index]["sports"][0]["slug"]
            schedules = await self._get_schedule(team_ids=list(teams.values()), sport=sport, league=league_name)
            players = await self._get_players(team_ids=list(teams.values()), sport=sport, league=league_name)

            for team_name, team_id in teams.items():
                mapping.setdefault(league_name, {})[team_name] = {
                    "id": team_id,
                    "players": players.get(team_id, []),
                    "schedule": schedules.get(team_id, [])
                }

        if mapping:
            await redis_instance.store_data(
                key_name="espn_mapping",
                data_to_store=mapping,
                key_expiration=21600 # 6 Hours
            )


    async def _get_players(self, team_ids: list, sport: str, league: str):
        tasks = [
            self.api_caller(
                book_name="ESPNMapper",
                session=self.session,
                url=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/roster?limit=5000",
                method="GET",
            )
            for team_id in team_ids
        ]

        results = await asyncio.gather(*tasks)

        player_mapping = {}

        for result in results:
            if not result:
                continue

            team_id = result.get("team", {}).get("id")
            for athlete in result.get("athletes", []):
                for player in (athlete.get("items") or [athlete]):
                    player_name = player.get("displayName")
                    if not player_name:
                        continue

                    player_mapping.setdefault(team_id, []).append(player_name)


        return player_mapping


    async def _get_schedule(self, team_ids: list, sport: str, league: str) -> dict:
        tasks = [
            self.api_caller(
                book_name="ESPNMapper",
                session=self.session,
                url=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule",
                method="GET",
            )
            for team_id in team_ids
        ]

        results = await asyncio.gather(*tasks)

        schedule_mapping = {}

        for result in results:
            if not result:
                continue

            team_id = result.get("team", {}).get("id")
            team_name = result.get("team", {}).get("displayName")

            for event in result.get("events", []):
                game_date = event.get("date")
                modified_game_date = datetime.strptime(game_date, "%Y-%m-%dT%H:%MZ").strftime("%Y-%m-%dT%H:%M:%SZ")

                split_teams = [team.strip() for team in re.split(r'at|vs\.?', event.get("name", ""), flags=re.IGNORECASE)]
                opponent = next((team for team in split_teams if team != team_name), None)
                schedule_mapping.setdefault(team_id, []).append({
                    "opponent": opponent,
                    "team": team_name,
                    "event_name": event.get("name"),
                    "date": modified_game_date
                })

        return schedule_mapping


    async def _get_teams(self) -> tuple:
        """
        Teams mapping function to get ESPN team IDs.
        :return: Returns a dictionary of team names to ESPN IDs
        """

        raw_teams = [
            self.api_caller(
                book_name="ESPNMapper",
                session=self.session,
                url=f"https://site.api.espn.com/apis/site/v2/sports/{teams['sport']}/{teams['espn_league']}/teams?limit=5000",
                method="GET",
            )

            for teams in self.ESPN_LEAGUES
        ]

        results = await asyncio.gather(*raw_teams)

        leagues = list(chain.from_iterable(
            result["sports"][0]["leagues"]
            for result in results
        ))

        return leagues, results




if __name__ == "__main__":
    async def main():
        async with aiohttp.ClientSession() as session:
            espn = ESPNMapper(session=session)
            await espn.run_mapping()

    asyncio.run(main())






