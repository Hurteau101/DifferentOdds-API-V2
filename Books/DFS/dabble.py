import asyncio
import re
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import GameData, TeamData, Stats, OptionalStatInformation
from Utils.request_caller import SportbookRequestType


class Dabble(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="dabble", request_type=SportbookRequestType.ASYNC)

    def _extract_teams(self, game_data: dict, player_data: dict, start_time: str) -> dict | None:
        def team_splitter(team_name):
            return [part.strip() for part in re.split(r'vs | @ ', team_name) if part.strip()]

        teams = team_splitter(game_data.get("name"))
        if not teams:
            return None

        teams = [team for team in teams]
        player_team = player_data.get("teamName")

        team_a = teams[0]
        team_b = teams[1] if len(teams) > 1 else None

        team_key = Dabble.generate_key([team_a, team_b, start_time]) if team_b else Dabble.generate_key([player_team, start_time])

        return {
            "team_a": team_a,
            "team_b": team_b,
            "team_key": team_key,
            "player_team": player_team
        }

    def _extract_game_data(self, game_data: dict, league_data: dict) -> list:
        valid_markets = {market.get("id"): market for market in game_data.get("markets") if market.get("isDisplayed")}
        prices = {price.get("selectionId"): price for price in game_data.get("prices")}
        market_names = {market.get("id"): market_name.get("name")
                        for market_name in game_data.get("marketGroupMappings")
                        for market in market_name.get("markets", [])}

        start_date = game_data.get("advertisedStart", "").split(".")[0]
        league_id = game_data.get("competitionId")

        # Find the league name from the league_data using the league_id
        league = next((
            league_name.get("displayName")
            for league_name in league_data.get("data").get("activeCompetitions", [])
            if league_id == league_name.get("id")
        ), None)

        # If league is not found in active competitions, use the league name from game_data
        if league:
            league = league.lower()
        else:
            league = game_data.get("competitionName").lower()

        merged_stats = {}
        for player in game_data.get("playerProps"):
            # Skip players with no valid market or price
            if valid_markets.get(player.get("marketId")) is None or prices.get(player.get("selectionId"), {}).get(
                    "price") is None:
                continue

            player_name = player.get("playerName", "")
            team_data = self._extract_teams(game_data, player, start_date)
            is_future = any(future in league.lower() for future in ["szn", "futures", "future"])

            player_key = (
                player_name,
                team_data.get("team_a"),
                team_data.get("team_b"),
                start_date
            )

            if player_key not in merged_stats:
                merged_stats[player_key] = GameData(
                    league=league,
                    game_key=team_data.get("team_key"),
                    start_date=start_date,
                    team_data=TeamData(
                        team_a=team_data.get("team_a"),
                        team_b=team_data.get("team_b"),
                    ),
                    future=is_future,
                    odds=[],
                    solo_game=False if all([team_data.get("team_a"), team_data.get("team_b")]) or is_future else True
                )

            stat_type = market_names.get(player.get("marketId"), "").lower()

            stat_obj = Stats(
                player_name=player_name,
                player_team=team_data.get("player_team"),
                stat_type=stat_type,
                line=player.get("value"),
                bet_type=player.get("lineType"),
                regular_line=False,
                optional_stats=OptionalStatInformation(
                    multiplier=prices.get(player.get("selectionId"), {}).get("price"),
                )
            )

            merged_stats[player_key].odds.append(stat_obj)

            # Create a list of the bet directions for the current player
            directions = [stat.bet_type for stat in merged_stats[player_key].odds if stat.stat_type == stat_type]

            # If there is both an "over" and "under" bet direction for the same stat type, mark it as a regular line
            if "over" in directions and "under" in directions:
                for stat in merged_stats[player_key].odds:
                    if stat.stat_type == stat_type:
                        stat.regular_line = True

        return list(merged_stats.values())

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            if not league_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned from main_url",
                    level="error"
                )
                return

            league_ids = [
                league.get("id")
                for league in league_data.get("data").get("activeCompetitions")
            ]

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("alternate_url").format(league_id=league_id),
                    method=self.book_data.method,
                )
                for league_id in league_ids
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            game_ids = set(
                game.get("id")
                for result in results
                if result
                for game in result.get("data", {})
            )

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("alternate_url_2").format(game_id=game_id),
                    method=self.book_data.method,
                )
                for game_id in game_ids
            ]

            results = await asyncio.gather(*tasks)

            if not results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No game ids returned",
                    level="error"
                )
                return

            # Flatten and filter out None results
            game_data_list = [
                result.get("data")
                for result in results if result and result.get("status") == "success"
            ]

            events = {}
            # Get all player data from the game data
            for games in game_data_list:
                for game_data in self._extract_game_data(games, league_data):
                    if game_data:
                        self.add_to_events(events, game_data, GameData)

            dabble_data = list(events.values())
            mapped_data = await self.external_mapper(dabble_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data