import asyncio
from datetime import datetime
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData, TeamData
from Utils.request_caller import SportbookRequestType


### AUTH REQUIREMENTS NOW -- NEED TO FIX ###

class Drafters(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="drafters", request_type=SportbookRequestType.ASYNC)

    def _extract_league_ids(self, league_data: dict) -> dict:
        return {
            int(league.get("id")): league.get("name")

            for league in league_data.get("entities")
        }

    def _extract_game_data(self, game_data: list, league_ids: dict) -> list:
        if not game_data:
            return []

        merged_players = {}

        for player in game_data:
            player_id = player["player_id"]
            player_name = player.get("player_name")
            league = league_ids.get(player.get("game_id"))
            league = league.lower() if league else "Unknown"
            team_a = player.get("event").get("home")
            team_b = player.get("event").get("away")
            player_team = player.get("event").get("own", {})

            start_date = player.get("event").get("start_time")
            start_date = datetime.fromtimestamp(start_date).isoformat()

            if team_a and team_b:
                team_key = Drafters.generate_key([team_a, team_b, start_date])
            else:
                team_key = Drafters.generate_key([player_name, start_date])

            stats = [
                DFSStats(
                    player_name=player_name,
                    player_team=player_team,
                    future=True if "season" in player.get("bid_stats_name").lower() else False,
                    stat_type=player.get("bid_stats_name"),
                    line=player.get("bid_stats_value"),
                    bet_type=option,
                    regular_line=True
                )
                for option in player.get("options")
            ]

            if player_id in merged_players:
                merged_players[player_id].odds.extend(stats)
            else:
                merged_players[player_id] = GameData(
                    league=league,
                    game_key=team_key,
                    start_date=start_date,
                    team_data=TeamData(
                        team_a=team_a,
                        team_b=team_b,
                    ),
                    odds=stats,
                    solo_game=False if all([team_a, team_b]) else True,
                )

        return list(merged_players.values())

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers
            )

            if not api_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="Main API URL returned no data",
                    level="error"
                )
                return

            league_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("alternate_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
                parse_json=True
            )

            if not league_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            league_ids = self._extract_league_ids(league_data)

            results = [
                self._extract_game_data(game_data=game.get("players"), league_ids=league_ids)
                for game in api_data.get("entities")
            ]

            events = {}
            for game_data in self.yield_game_data(book_data=results):
                self.add_to_events(events, game_data, GameData)

            drafters_data = list(events.values())
            mapped_data = await self.map_runner(session=session, sportsbook_data=drafters_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data
