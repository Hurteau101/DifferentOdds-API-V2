import re
import aiohttp
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.book_base import SportbookRequestType
import asyncio

class Dabble(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.SPOOF, sportsbook_name="dabble")

    def _extract_teams(self, game_data, player_data, start_time):
        def team_splitter(team_name):
            return [part.strip() for part in re.split(r'vs | @ ', team_name) if part.strip()]

        teams = team_splitter(game_data.get("name"))
        if not teams:
            return None

        teams = [self.clean_and_normalize_name(team) for team in teams]
        player_team = self.clean_and_normalize_name(player_data.get("teamName"))

        team_a = teams[0]
        team_b = teams[1] if len(teams) > 1 else None

        team_key = self._generate_key([team_a, team_b, start_time]) if team_b else self._generate_key(
            [player_team, start_time])

        return {
            "team_a": team_a,
            "team_b": team_b,
            "team_key": team_key,
            "player_team": player_team
        }

    def _extract_game_data(self, game_data, league_data):
        valid_markets = {market.get("id"): market for market in game_data.get("markets") if market.get("isDisplayed")}
        prices = {price.get("selectionId"): price for price in game_data.get("prices")}
        market_names = {market.get("id"): market_name.get("name")
                        for market_name in game_data.get("marketGroupMappings")
                        for market in market_name.get("markets", [])}

        start_date = self.cache_time(game_data.get("advertisedStart", "").split(".")[0])
        league_id = game_data.get("competitionId")

        # Find the league name from the league_data using the league_id
        league = next((
            league_name.get("displayName")
            for league_name in league_data.get("data").get("activeCompetitions", [])
            if league_id == league_name.get("id")
        ), None)


        # If league is not found in active competitions, use the league name from game_data
        if league:
            league = LEAGUES.get(league.lower(), league.upper())
        else:
            league = LEAGUES.get(game_data.get("competitionName").lower(), game_data.get("competitionName").upper())

        merged_stats = {}
        for player in game_data.get("playerProps"):
            # Skip players with no valid market or price
            if valid_markets.get(player.get("marketId")) is None or prices.get(player.get("selectionId"), {}).get(
                    "price") is None:
                continue

            player_name = self.clean_and_normalize_name(player.get("playerName", ""))
            team_data = self._extract_teams(game_data, player, start_date)
            is_future = any(
                future in league.lower() for future in ["szn", "futures", "future"])

            player_key = (
                player_name,
                team_data.get("team_a"),
                team_data.get("team_b"),
                start_date
            )

            if player_key not in merged_stats:
                merged_stats[player_key] = PlayerData(
                    player_name=player_name,
                    league=league,
                    start_date=start_date,
                    team_data=TeamData(
                        team_a=team_data.get("team_a"),
                        team_b=team_data.get("team_b"),
                        team_key=team_data.get("team_key"),
                        player_team=team_data.get("player_team")
                    ),
                    future=is_future,
                    stats=[],
                    solo_game=False if all([team_data.get("team_a"), team_data.get("team_b")]) or is_future else True
                )

            stat_type = STAT_TYPES.get(market_names.get(player.get("marketId"), "").lower(),
                                       market_names.get(player.get("marketId"), "")).title()

            stat_obj = Stats(
                stat_type=stat_type,
                line=player.get("value"),
                bet_direction=player.get("lineType"),
                regular_line=False,
                optional_stats= OptionalStatInformation(
                    multiplier=prices.get(player.get("selectionId"), {}).get("price"),
                )
            )

            merged_stats[player_key].stats.append(stat_obj)

            # Create a list of the bet directions for the current player
            directions = [stat.bet_direction for stat in merged_stats[player_key].stats if stat.stat_type == stat_type]

            # If there is both an "over" and "under" bet direction for the same stat type, mark it as a regular line
            if "over" in directions and "under" in directions:
                for stat in merged_stats[player_key].stats:
                    if stat.stat_type == stat_type:
                        stat.regular_line = True

        return list(merged_stats.values())


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            print(league_data)

            if not league_data:
                self.file_logger.log(
                    message="Couldn't map leagues for Dabble",
                )
                return None

            league_ids = [
                league.get("id")
                for league in league_data.get("data").get("activeCompetitions")
            ]

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("alternate_url").format(league_id=league_id),
                    method=self.book_data.method,
                )
                for league_id in league_ids
            ]

            results = await asyncio.gather(*tasks)

            game_ids = set(
                game.get("id")
                for result in results
                if result
                for game in result.get("data", {})
            )

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("alternate_url_2").format(game_id=game_id),
                    method=self.book_data.method,
                )
                for game_id in game_ids
            ]

            results = await asyncio.gather(*tasks)

            # Flatten and filter out None results
            game_data_list = [
                result.get("data")
                for result in results if result and result.get("status") == "success"
            ]

            # Get all player data from the game data
            player_list = [
                player
                for game_details in game_data_list
                for player in self._extract_game_data(game_details, league_data)
            ]

            print(player_list)

            return await self._database_mapper(player_list)


if __name__ == "__main__":
    dabble = Dabble()
    data = asyncio.run(dabble.run_book())

