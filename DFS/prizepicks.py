import asyncio
from Settings.proxy_manger import ProxyManager
import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase


class Prizepicks(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="prizepicks")
        self.esport_leagues = ["CS2", "LOL", "DOTA2", "VAL", "COD"]


    def _map_info(self, api_data):
        """Map the player and team information"""
        player_info = {
            player.get("id"): player
            for player in api_data.get("included")
            if player.get("type") == "new_player" and "attributes" in player
        }

        team_info = {
            team["id"]: team["attributes"]
            for team in api_data.get("included")
            if team.get("type") == "team"
        }
        return player_info, team_info


    def _extract_player_data(self, game_details, player_info_map, team_info_map):
        """Extract all the player data"""
        unique_id = game_details.get("id")

        player_id = game_details.get("relationships", {}).get("new_player", {}).get("data", {}).get("id")
        team_id = player_info_map.get(player_id, {}).get("relationships", {}).get("team_data", {}).get("data", {}).get(
            "id")

        game_attrs = game_details.get("attributes", {})
        start_date = self.cache_time(game_attrs.get("start_time"))
        player_info = player_info_map.get(player_id, {}).get("attributes", {})
        # team_details = team_info_map.get(team_id, {})
        player_url = player_info.get("image_url", "").replace("\t", "") if player_info.get("image_url") else ""

        if not player_id or not team_id:
            return None

        extracted_info = {
            "player_name": player_info.get("display_name", ""),
            "league": player_info.get("league"),
            **self.__get_teams(player_info, game_attrs, start_date),
        }

        processed_stats = [
            Stats(
                regular=stat.get("regular"),
                stat_type=stat.get("stat_type").title(),
                line=stat.get("line"),
                bet_type=stat.get("bet_type"),
                optional_stats=OptionalStats(
                    projection_id=unique_id,
                    odds_type=stat.get("odds_type"),
                    market_type=stat.get("market_type"),
                    betlink=stat.get("betlink", {}),
                    discount_name=stat.get("discount_name"),
                    discount_percentage=stat.get("discount_percentage"),
                )
            )
            for stat in self.__process_stats(game_attrs, extracted_info["league"], unique_id)
        ]

        return PlayerData(
            **extracted_info,
            start_date=start_date,
            stats=processed_stats,
            optional_player_data=OptionalPlayerData(
                player_id=unique_id,
                player_image_url=player_url,
                game_id=game_attrs.get("game_id"),
            )
        )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            proxy_manger = ProxyManager(self.api_caller)
            api_data = await proxy_manger.proxy_controller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            if not api_data:
                self._api_call_log("prizepicks")
                return

            player_info_map, team_info_map = self._map_info(api_data)

            player_data_dict = {}

            for game_details in api_data("data", []):
                player_data = self._extract_player_data(game_details, player_info_map, team_info_map)

                if player_data:
                    player_key = (
                        player_data.player_name,
                        player_data.team_a,
                        player_data.team_b,
                        player_data.start_date,
                    )

                    if player_key in player_data_dict:
                        player_data_dict[player_key].stats.extend(player_data.stats)
                    else:
                        player_data_dict[player_key] = player_data


if __name__ == "__main__":
    prizepicks = Prizepicks()
    asyncio.run(prizepicks.run_book())
