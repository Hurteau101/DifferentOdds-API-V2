# import asyncio
# import json
# import os
# from itertools import zip_longest, batched
# from typing import Optional, Callable
# # from Books.Bases.book_base import BookBase
# from Internal_Mapping.find_mapping import FindMapper
# from Monitoring.monitoring import create_sentry_message
# from Redis.redis_manager import RedisAsyncManager, RedisSyncManager, static_mapping_service
# from Utils.helpers import ordinal_formatter
# from Utils.request_caller import APICaller
# from curl_cffi import AsyncSession as CurlAsyncSession
#
# class BettoroddsMapping(APICaller):
#     def __init__(self, payload_batch: int, async_batch: int, book_name: str):
#         self.payload_batch = payload_batch # Used for batching the payload.
#         self.async_batch = async_batch # Used for BettorOdds API batching
#         self.book_name = book_name
#         self.redis_instance = RedisAsyncManager(database=4)
#         self.league_mapping = static_mapping_service.get().get("leagues", {})
#         super().__init__()
#
#     def solo_mapper(self, stats: DFSStats, game_data: GameData, mapped_players: dict):
#         """Maps the player's name in the game data if it matches a solo game."""
#
#         def find_player(player_name: str):
#             player_key = f"{player_name.lower()}-{game_data.league.lower()}"
#             return mapped_players.get(player_key)
#
#         def map_team(team: str):
#             if not team:
#                 return team
#
#             team = team.lower()
#
#             found_dict = next((
#                 player
#                 for player in mapped_players.values()
#                 if player.get("original_name").lower() == team or team.lower() in player.get("original_name").lower()
#             ), None)
#
#             return found_dict.get("player_name") if found_dict else team
#
#         for stat in stats:
#             found_player = find_player(player_name=stat.player_name)
#
#             if found_player:
#                 player_name = found_player.get("player_name")
#                 stat.player_name = player_name
#                 game_data.league = found_player["league"]
#                 game_data.player_team = player_name
#
#         team_a = game_data.team_data.team_a
#         team_b = game_data.team_data.team_b
#
#         if team_a and team_b:
#             for side in ["team_a", "team_b"]:
#                 team_name_attr = getattr(game_data.team_data, side, None)
#                 team_name = map_team(team_name_attr)
#                 if not team_name:
#                     continue
#
#                 setattr(game_data.team_data, side, team_name)
#
#             game_data.event_name = " vs ".join(sorted([game_data.team_data.team_a, game_data.team_data.team_b]))
#             game_data.game_key = self.generate_key(
#                 [game_data.team_data.team_a, game_data.team_data.team_b, game_data.start_date])
#
#     def map_data(self, original_sportsbook_data: list, mapped_teams: dict, mapped_players: dict, mapped_markets: dict,
#                  solo_game_mapper_func: Optional[Callable] = None):
#
#         for data in original_sportsbook_data:
#             solo_game = getattr(data, "solo_game", False)
#             if solo_game and solo_game_mapper_func:
#                 solo_game_mapper_func(
#                     stats=data.odds,
#                     game_data=data,
#                     mapped_players=mapped_players
#                 )
#
#                 continue
#
#             for side in ["team_a", "team_b"]:
#                 league = data.league
#                 team_name_attr = getattr(data.team_data, side, None)
#                 if not team_name_attr:
#                     continue
#
#                 team_key = f"{team_name_attr.lower()}-{league.lower()}"
#                 found_team = mapped_teams.get(team_key)
#                 if found_team:
#                     data.league = found_team["league"]
#                     setattr(data.team_data, side, found_team["team_name"])
#                     setattr(data.team_data, f"{side}_abbreviation", found_team.get("abbreviation"))
#
#                     for stats in data.odds:
#                         if getattr(stats, "player_team", None):
#                             attr_name = "player_team"
#                         elif getattr(stats, "bet_team", None):
#                             attr_name = "bet_team"
#                         else:
#                             continue
#
#                         team_value = getattr(stats, attr_name)
#
#                         if team_value and team_value.lower() == found_team["original_name"].lower():
#                             setattr(stats, attr_name, found_team["team_name"])
#
#
#             data.game_key = BookBase.generate_key(
#                 [data.team_data.team_a, data.team_data.team_b, data.start_date])
#
#             if data.team_data.team_a and data.team_data.team_b:
#                 data.event_name = " vs ".join(sorted([data.team_data.team_a, data.team_data.team_b]))
#
#             for stats in data.odds:
#                 if getattr(stats, "stat_type", None):
#                     attr_name = "stat_type"
#                 elif getattr(stats, "market", None):
#                     attr_name = "market"
#                 else:
#                     continue
#
#                 stat_value = getattr(stats, attr_name)
#
#                 stat_key = f"{stat_value.lower()}-{league.lower()}"
#
#                 if stat_key in mapped_markets:
#                     setattr(stats, attr_name, mapped_markets[stat_key])
#
#         return original_sportsbook_data
#
#     async def team_look_up(self, team_data: list) -> dict:
#         """Look up the teams and return the dict build for players and teams"""
#         mapper = FindMapper()
#         mapped_teams = await mapper.controller(team_data=team_data)
#
#         def create_key(data: dict) -> str:
#             return f'{data["original_name"].lower()}-{data["league"].lower()}'
#
#         def create_build(data: dict) -> dict:
#             return {
#                 **(
#                     {"team_name": data.get("team_name")}
#                     if not data.get("solo_game")
#                     else {
#                         "player_name": data.get("team_name")
#                     }
#                 ),
#                 "league": data.get("league"),
#                 "original_league": data.get("original_league"),
#                 "original_name": data.get("original_name"),
#                 "source": "Internal"
#             }
#
#         return {
#             "players": {create_key(player): create_build(player) for player in mapped_teams if player.get("solo_game")},
#             "teams": {create_key(team): create_build(team) for team in mapped_teams if not team.get("solo_game")},
#         }
#
#     def check_team_in_bettorodds(self, teams: dict, name_to_check: str):
#         name_to_check = name_to_check.lower()
#
#         return any(
#             name_to_check == mapped.get("original_name", "").lower()
#             or name_to_check == mapped.get("team_name", "").lower()
#             for mapped in teams.values()
#         )
#
#     def unique_teams_helper(self, raw_unique_data_passer: list, sportsbook_name: str) -> list[dict]:
#         """Helper to build a unique team list from raw data"""
#         seen = set()
#         team_data = []
#
#         for data in raw_unique_data_passer:
#             if any([data.get("future", False), data.get("live", False), data.get("combo", False)]):
#                 continue
#
#             player_name = data.get("player_name")
#             league = data.get("league")
#             solo_game = data.get("solo_game", False)
#
#             if solo_game:
#                 if not player_name or not league:
#                     continue
#
#                 key = (player_name.lower(), league.lower())
#                 if key not in seen:
#                     seen.add(key)
#                     team_data.append({
#                         "team_name": player_name.strip(),
#                         "league": league,
#                         "solo_game": solo_game,
#                         "sportsbook": sportsbook_name
#                     })
#
#                     continue
#             team_a = data.get("team_a")
#             team_b = data.get("team_b")
#
#             if not team_a and not team_b:
#                 continue
#
#             for team in (team_a, team_b):
#                 if team and team.strip():
#                     if not league:
#                         continue
#
#                     key = (team.lower(), league.lower())
#                     if key not in seen:
#                         seen.add(key)
#                         team_data.append({
#                             "team_name": team.strip(),
#                             "league": league,
#                             "solo_game": solo_game,
#                             "sportsbook": sportsbook_name
#                         })
#
#         return team_data
#
#     def _map_teams_players(self, data: dict, collection_key: str, league: str) -> dict:
#         """Maps the leagues and players from BettorOdds API"""
#         mapped = {
#             "mapped": {},
#             "unmapped": {}
#         }
#
#         for key, value in data.items():
#             if not value:
#                 mapped["unmapped"][key] = league
#                 continue
#
#             original = value.get("query")
#
#             if not original:
#                 mapped["unmapped"][key] = league
#
#             found = next(
#                 (
#                     item
#                     for item in value.get(collection_key, [])
#                     if item.get("league").lower() == league.lower() or item.get("sport").lower() == league.lower()
#                 ),
#                 None,
#             )
#
#             if found:
#                 mapped["mapped"][f"{original}-{league}".lower()] = {
#                     **(
#                         {"team_name": found.get("normalized_name")} if collection_key == "teams"
#                         else {"player_name": found.get("normalized_name")}
#                     ),
#                     "league": found.get("league"),
#                     "original_league": league.upper(),
#                     "original_name": original.lower(),
#                     "source": "External"
#                 }
#             else:
#                 mapped["unmapped"][original] = league
#
#         return mapped
#
#     def _map_markets(self, data: dict, league: str) -> dict:
#         """Maps the markets from BettorOdds API"""
#
#         mapped = {
#             "mapped": {},
#             "unmapped": {}
#         }
#
#         league_upper = league.upper()
#         league_lower = league.lower()
#
#         sport = self.league_mapping.get(league_upper, {}).get("sport")
#         sport_lower = sport.lower() if sport else None
#
#         for value in data.values():
#             if not value:
#                 continue
#
#             original = value.get("query")
#             normalized = value.get("normalized_name")
#             match_list = value.get("matches", [])
#
#             if match_list and sport_lower:
#                 normalized = next(
#                     (
#                         match.get("normalized_name")
#                         for match in match_list
#                         if any(s.lower() == sport_lower for s in match.get("sports", []))
#                     ),
#                     normalized
#                 )
#
#                 print("Normalized Found", normalized)
#
#             if original and normalized:
#                 mapped["mapped"][f"{original.lower()}-{league_lower}"] = ordinal_formatter(normalized.lower()) if normalized else None
#             elif original:
#                 mapped["unmapped"][original] = league
#
#         return mapped
#
#     def map_bettorodds(self, bettorodds_data: dict, league: str):
#         """Map the bettorodds data and return it in a standard formulized dictionary."""
#         if not bettorodds_data:
#             return {}
#
#         players = bettorodds_data.get("player", {})
#         teams = bettorodds_data.get("team", {})
#         market = bettorodds_data.get("market", {})
#
#
#         return {
#             "teams": self._map_teams_players(data=teams, collection_key="teams", league=league),
#             "players": self._map_teams_players(data=players, collection_key="players", league=league),
#             "markets": self._map_markets(data=market, league=league),
#         }
#
#     async def build_payload(self, sportsbook_data: list) -> dict:
#         def create_key(raw_name: str, league: str):
#             return f"{raw_name.lower().strip()}-{league.lower().strip()}"
#
#         mapping_dict = {}
#
#         for data in sportsbook_data:
#             league = data.league
#
#             mapping_dict.setdefault(
#                 league,
#                 {
#                     "teams": set(),
#                     "players": set(),
#                     "markets": set(),
#                 }
#             )
#
#             for team in (data.team_data.team_a, data.team_data.team_b):
#                 if team and not await self.redis_instance.is_seen("seen_teams", create_key(team, league)):
#                     mapping_dict[league]["teams"].add(team)
#
#             for odds in data.odds:
#                 player_name = getattr(odds, "player_name", None) or getattr(odds, "bet_player", None)
#                 stat_type = getattr(odds, "stat_type", None) or getattr(odds, "market", None)
#
#
#                 if player_name and not await self.redis_instance.is_seen(
#                         "seen_players", create_key(player_name, league)
#                 ):
#                     mapping_dict[league]["players"].add(player_name)
#
#                 if stat_type and not await self.redis_instance.is_seen(
#                         "seen_markets", create_key(stat_type, league)
#                 ):
#                     mapping_dict[league]["markets"].add(stat_type)
#
#         batched_data = {
#             league: {
#                 k: list(batched(v, self.payload_batch))
#                 for k, v in league_data.items()
#             }
#             for league, league_data in mapping_dict.items()
#         }
#
#         return {
#             league: [
#                 {
#                     "team": list(teams) or [],
#                     "player": list(players) or [],
#                     "market": list(markets) or [],
#                 }
#                 for teams, players, markets in zip_longest(
#                     league_data.get("teams", []),
#                     league_data.get("players", []),
#                     league_data.get("markets", []),
#                     fillvalue=[]
#                 )
#             ]
#             for league, league_data in batched_data.items()
#         }
#
#     async def bettorodds_api_caller(self, session: CurlAsyncSession, payload: dict, league: str):
#         if not payload:
#             return None
#
#         api_key = os.getenv("INTERNAL_BETTORODDS_MAPPER_API_KEY")
#
#         if not api_key:
#             create_sentry_message(
#                 tag_key="BettorOdds Mapper",
#                 tag_value="api_failure",
#                 message="No API key provided.",
#                 level="error"
#             )
#
#             return None
#
#         api_data = await self.api_caller(
#             session=session,
#             url="https://cache-api.eternitylabs.co/cache/batch",
#             method="POST",
#             headers={
#                 "Authorization": f"Bearer {api_key}",
#             },
#             json=payload
#         )
#
#         return self.map_bettorodds(bettorodds_data=api_data, league=league)
#
#     async def run_mapping(self, sportsbook_data: list, session: CurlAsyncSession) -> dict:
#         if not sportsbook_data:
#             return {}
#
#         previously_stored = {
#             name: await self.redis_instance.get_hset(name)
#             for name in ["players", "markets", "teams"]
#         }
#
#         # print(f'''
#         # - Previous Team Length: {len(previously_stored.get("teams"))}\n
#         # - Previous Player Length: {len(previously_stored.get("players"))}\n
#         # - Previous Market Length: {len(previously_stored.get("markets"))}\n\n
#         # ''')
#
#         payload_batch = await self.build_payload(sportsbook_data=sportsbook_data)
#
#         for league, league_data in payload_batch.items():
#             teams = set()
#             players = set()
#             markets = set()
#
#             for item in league_data:
#                 teams.update(item["team"])
#                 players.update(item["player"])
#                 markets.update(item["market"])
#
#             await self.redis_instance.add_seen(
#                 "seen_teams",
#                 [f"{t.strip().lower()}-{league.lower()}" for t in teams],
#             )
#
#             await self.redis_instance.add_seen(
#                 "seen_players",
#                 [f"{p.strip().lower()}-{league.lower()}" for p in players],
#             )
#
#             await self.redis_instance.add_seen(
#                 "seen_markets",
#                 [f"{m.strip().lower()}-{league.lower()}" for m in markets],
#             )
#
#         results = []
#
#         for league, league_data in payload_batch.items():
#             for i in range(0, len(league_data), self.async_batch):
#                 # print(f"Running Mapping [{league}] {i}")
#                 batch = league_data[i: i + self.async_batch]
#                 # print(f"Processing {league} batch {i} to {i + self.async_batch}")
#
#                 tasks = [
#                     self.bettorodds_api_caller(
#                         session=session,
#                         payload=payload,
#                         league=league
#                     )
#                     for payload in batch
#                 ]
#
#                 results.extend(await asyncio.gather(*tasks))
#
#         breakdown_results = {
#             side: {
#                 category: {
#                     k: v
#                     for result in results
#                     for k, v in result.get(category, {}).get(side, {}).items()
#                 }
#                 for category in ("teams", "players", "markets")
#             }
#             for side in ("mapped", "unmapped")
#         }
#
#         categories = ("teams", "players", "markets")
#
#         for category in categories:
#             mapped = breakdown_results["mapped"][category]
#
#             await self.redis_instance.store_mappings(
#                 f"{category}",
#                 mapped
#             )
#
#         final_results = {
#             category: {
#                 **previously_stored.get(category, {}),
#                 **breakdown_results["mapped"].get(category, {})
#             }
#             for category in ("teams", "players", "markets")
#         }
#
#         # print(final_results)
#         # return final_results
#         # return breakdown_results.get("mapped", {})
#
#         return final_results
#
#
#
#
#
#
