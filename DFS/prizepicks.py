import asyncio
import re

from Mapper.static_mapper import STAT_TYPES
from Settings.dfs_model import Stats, PlayerData, TeamData, Discounts, OptionalStatInformation
from Settings.proxy_manger import ProxyManager
import aiohttp
from Settings.book_base import SportbookRequestType, BookBase
from Settings.dfs_book_base import DFSBookBase


class Prizepicks(DFSBookBase):
    SOLO_GAMES = [
        "MMA", "TENNIS"
    ]

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

    def _opponent_extractor(self, league, opponent):
        # Pass in league due to the way Prizepicks has there opponent data.
        if league in self.esport_leagues:
            opponent = re.split(r'\bMAPS?\b', opponent, flags=re.IGNORECASE)[0].strip()
        else:
            opponent = re.split(r'\b(at|vs)\b|\d', opponent, flags=re.IGNORECASE)[0].strip()

        if opponent:
            self.clean_and_normalize_name(opponent)

        return opponent

    def _process_stats(self, game_attrs, league_name, projection_id):
        """Process the stats for the player"""

        stat_type = game_attrs.get("stat_type", "").replace("\t", " ").strip().lower()
        if "+" in stat_type:
            split_words = stat_type.split("+")
            valid_words = [self.STAT_TYPES.get(word.strip(), stat_type) for word in split_words if
                           self.STAT_TYPES.get(word.strip())]
            if valid_words:
                stat_type = " + ".join(valid_words)

        extracted_stats = {
            "regular": True if game_attrs.get("odds_type", "").lower() == "standard" and not game_attrs.get(
                "flash_sale_line_score") and not "1+2+3" in game_attrs.get("stat_display_name") else False,
            "stat_type": self.STAT_TYPES.get(stat_type.lower(), stat_type).title(),
            "odds_type": game_attrs.get("odds_type", "").lower() if not '1+2+3' in game_attrs.get("stat_display_name",
                                                                                                  "").lower() else "MLBLive",
            "line": game_attrs.get("flash_sale_line_score") or game_attrs.get("line_score"),
            "market_type": league_name if any(char.isdigit() for char in league_name) else "full",
        }

        if game_attrs.get("flash_sale_line_score"):
            extracted_stats.update({
                "discount_name": game_attrs.get("discount_name"),
                "discount_percentage": game_attrs.get("discount_percentage"),
            })

        bet_direction = ["over", "under"] if "discount_name" not in extracted_stats and extracted_stats[
            "odds_type"] == "standard" else ["over"]

        return [{
            **extracted_stats,
            "bet_direction": bet,
            "betlink": {
                "raw_projection_id": projection_id,
                "id": f"{projection_id}-{bet[0]}-{extracted_stats['line']}",
                "base": "https://app.prizepicks.com/?projections=",
                "url": f'https://app.prizepicks.com/?projections={projection_id}-{bet[0]}-{extracted_stats["line"]}',
                "side": bet,
            }
        } for bet in bet_direction]


    def _extract_data(self, game_details, player_info_map):
        """Extract all the player data"""
        player_id = game_details.get("relationships", {}).get("new_player", {}).get("data", {}).get("id")
        team_id = player_info_map.get(player_id, {}).get("relationships", {}).get("team_data", {}).get("data", {}).get(
            "id")

        # Fallback if team_id is not found in relationships
        if not team_id:
            team_id = player_info_map.get(player_id, {}).get("attributes", {}).get("team") if (
                player_info_map.get(player_id, {}).get("attributes", {}).get("team")) \
                else player_info_map.get(player_id, {}).get("attributes", {}).get("team_name")

        if not player_id or not team_id:
            return None

        player_information = player_info_map.get(player_id, {}).get("attributes", {})
        game_information = game_details.get("attributes", {})


        player_name = player_information.get("display_name", "") if player_information.get("display_name") != "" \
            else player_information.get("name", "")

        raw_league =  player_information.get("league").upper() if player_information.get("league") else None

        league = self.LEAGUE_MAPPING.get(raw_league.lower(), raw_league.upper())


        projection_id = game_details.get("id")
        start_date = self.cache_time(game_information.get("start_time"))
        team = self.clean_and_normalize_name(player_information.get("team"))
        opponent = self.clean_and_normalize_name(self._opponent_extractor(league=league, opponent=game_information.get("description")))
        future = True if "szn" in game_information.get("description").lower() or "szn" in league.lower() else False
        combo = True if "combo" in game_information.get("stat_type").lower() else False
        live = True if league.lower() == "mlblive" else False

        if team and opponent:
            team_key = BookBase._generate_key([team, opponent, start_date])
        else:
            team_key = BookBase._generate_key([player_name, start_date])

        stats = [
            Stats(
                stat_type=STAT_TYPES.get(stat.get("stat_type"), stat.get("stat_type")).title(),
                line=stat.get("line"),
                bet_direction=stat.get("bet_direction"),
                regular_line=stat.get("regular"),
                discounts=Discounts(
                    discount_name=stat.get("discount_name"),
                    discount_percentage=stat.get("discount_percentage")
                ),
                optional_stats=OptionalStatInformation(
                    odds_type=stat.get("odds_type"),
                    market_type=stat.get("market_type"),
                    betlink=stat.get("betlink")
                )
            )

            for stat in self._process_stats(game_information, raw_league, projection_id)
        ]

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_name),
            league=league,
            start_date=start_date,
            team_data=TeamData(
                team_a=team,
                team_b=opponent,
                team_key=team_key,
                player_team=team
            ),
            future=future,
            solo_game=True if league in Prizepicks.SOLO_GAMES else False,
            stats=stats,
            combo=combo,
            live=live
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            proxy_manger = ProxyManager(self.api_caller)
            raw_api_data = await proxy_manger.proxy_controller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                sportsbook="prizepicks",
            )

            api_data = self.check_api_response(sportsbook="prizepicks", results=raw_api_data)

            if not api_data:
                return
    
            player_info_map, team_info_map = self._map_info(api_data)
            player_data_list = {}

            for game_details in api_data.get("data", []):
                player_data = self._extract_data(game_details, player_info_map)
                if player_data:
                    player_key = (
                        player_data.player_name,
                        player_data.team_data.team_a,
                        player_data.team_data.team_b,
                        player_data.start_date,
                    )

                    if player_key in player_data_list:
                        player_data_list[player_key].stats.extend(player_data.stats)
                    else:
                        player_data_list[player_key] = player_data

            prizepick_data = list(player_data_list.values())
            return await self._database_mapper(prizepick_data)




if __name__ == "__main__":
    prizepicks = Prizepicks()
    asyncio.run(prizepicks.run_book())
