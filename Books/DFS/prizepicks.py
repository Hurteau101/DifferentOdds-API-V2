import asyncio
import re
import aiohttp
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats, Discounts, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData, get_static_mapping
from Books.Bases.dfs_book_base import DFSBookBase
from Utils.proxy_manger import ProxyManager
from Utils.request_caller import SportbookRequestType


class Prizepicks(DFSBookBase):
    SOLO_GAMES = [
        "MMA", "TENNIS"
    ]
    def __init__(self):
        super().__init__(book_name="prizepicks", request_type=SportbookRequestType.ASYNC)

    def _map_info(self, api_data: dict) -> tuple:
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

    def _opponent_extractor(self, league: str, opponent: str) -> str:
        # Pass in league due to the way Prizepicks has there opponent data.
        if league in self.esport_leagues:
            opponent = re.split(r'\bMAPS?\b', opponent, flags=re.IGNORECASE)[0].strip()
        else:
            opponent = re.split(r'\b(at|vs)\b|\d', opponent, flags=re.IGNORECASE)[0].strip()

        return opponent

    def _process_stats(self, game_attrs: dict, league_name: str, projection_id: str | int) -> list:
        """Process the stats for the player"""

        stat_type = game_attrs.get("stat_type", "").replace("\t", " ").strip().lower()
        if "+" in stat_type:
            split_words = stat_type.split("+")
            valid_words = [word.strip() for word in split_words if word]
            if valid_words:
                stat_type = " + ".join(valid_words)

        extracted_stats = {
            "regular": True if game_attrs.get("odds_type", "").lower() == "standard" and not game_attrs.get(
                "flash_sale_line_score") and not "1+2+3" in game_attrs.get("stat_display_name") else False,
            "stat_type": stat_type,
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

    def _extract_data(self, game_details: dict, player_info_map: dict, static_league_mapping: dict) -> GameData | None:
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

        raw_league = player_information.get("league").upper() if player_information.get("league") else None

        league = static_league_mapping.get(raw_league.lower(), {}).get("mapped_name", raw_league.upper())

        projection_id = game_details.get("id")
        start_date = game_information.get("start_time")
        team = player_information.get("team")
        opponent = self._opponent_extractor(league=league, opponent=game_information.get("description"))



        future = True if "szn" in game_information.get("description").lower() or "szn" in league.lower() else False
        combo = True if "combo" in game_information.get("stat_type").lower() else False
        live = True if league.lower() == "mlblive" else False

        if team and opponent:
            team_key = Prizepicks.generate_key([team, opponent, start_date])
        else:
            team_key = Prizepicks.generate_key([player_name, start_date])

        stats = [
            DFSStats(
                player_name=player_name,
                player_team=team,
                combo=combo,
                live=live,
                stat_type=stat.get("stat_type"),
                line=stat.get("line"),
                future=future,
                bet_type=stat.get("bet_direction"),
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

        return GameData(
            league=league,
            game_key=team_key,
            start_date=start_date,
            team_data=TeamData(
                team_a=team,
                team_b=opponent,
            ),
            solo_game=True if league in Prizepicks.SOLO_GAMES else False,
            odds=stats,
        )

    async def run_book(self):
        timeout = aiohttp.ClientTimeout(
            total=300,
            connect=20,
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            proxy_manger = ProxyManager(self.api_caller)
            api_data = await proxy_manger.proxy_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
            )

            if not api_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="Main API URL returned no data",
                    level="error"
                )
                return

            player_info_map, team_info_map = self._map_info(api_data)
            static_mapping = get_static_mapping().get("leagues", {}) or {}

            events = {}
            for game_details in api_data.get("data", []):
                player_data = self._extract_data(game_details, player_info_map, static_mapping)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            prizepick_data = list(events.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=prizepick_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data

if __name__ == "__main__":
    pp = Prizepicks()
    asyncio.run(pp.run_book())