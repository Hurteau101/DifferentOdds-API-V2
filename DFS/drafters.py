from datetime import datetime

import aiohttp
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.book_base import BookBase, SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import Stats, PlayerData, TeamData


class Drafters(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="drafters")
        self.league_data = {}

    def _extract_league_ids(self, league_data):
        self.league_data.update({
                int(league.get("id")): league.get("name")

            for league in league_data.get("entities")
        })

    def _extract_game_data(self, game_data):
        if not game_data:
            return []

        merged_players = {}

        for player in game_data:
            player_id = player["player_id"]
            player_name = self.clean_and_normalize_name(player.get("player_name"))
            league = self.league_data.get(player.get("game_id"))
            league = LEAGUES.get(league.lower(), league) if league else "Unknown"
            team_a = self.clean_and_normalize_name(player.get("event").get("home"))
            team_b = self.clean_and_normalize_name(player.get("event").get("away"))
            player_team = self.clean_and_normalize_name(player.get("event").get("own", {}))

            start_date = player.get("event").get("start_time")
            start_date = self.cache_time(datetime.fromtimestamp(start_date).isoformat())

            if team_a and team_b:
                team_key = self._generate_key([team_a, team_b, start_date])
            else:
                team_key = self._generate_key([player_name, start_date])


            stats = [
                Stats(
                    stat_type=STAT_TYPES.get(player.get("bid_stats_name").lower(), player.get("bid_stats_name")).title(),
                    line=player.get("bid_stats_value"),
                    bet_direction=option,
                    regular_line=True
                )
                for option in player.get("options")
            ]

            if player_id in merged_players:
                merged_players[player_id].stats.extend(stats)
            else:
                merged_players[player_id] = PlayerData(
                    player_name=player_name,
                    league=league,
                    start_date=start_date,
                    team_data=TeamData(
                        team_a=team_a,
                        team_b=team_b,
                        player_team=player_team,
                        team_key=team_key
                    ),
                    future=True if "season" in player.get("bid_stats_name").lower() else False,
                    stats=stats,
                    solo_game=False if all([team_a, team_b]) else True,
                )

        return list(merged_players.values())

    async def run_book(self):
       async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers
            )

            if not api_data:
                self._api_call_log("drafters")
                return

            leagues = await self.api_caller(
                session=session,
                url=self.book_data.url.get("alternate_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
                parse_json=True
            )

            self._extract_league_ids(leagues)

            if not self.league_data:
                self._api_call_log("drafters")
                return

            results = [
                self._extract_game_data(game_data=game.get("players"))
                for game in api_data.get("entities")
            ]

            results = [player for sublist in results for player in sublist]

            data = await self._database_mapper(results)
            data = self._serialize_data(data)
            with open("drafters_data.json", "w") as file:
                import json
                json.dump(data, file, indent=4)

if __name__ == "__main__":
    drafters = Drafters()
    import asyncio
    asyncio.run(drafters.run_book())