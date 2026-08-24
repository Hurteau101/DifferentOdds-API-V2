from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Callable
import aiohttp
from Internal_Mapping.bettorodds_mapping import BettoroddsMapping
from Internal_Mapping.find_mapping import FindMapper
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import APICaller
from Redis.redis_manager import RedisAsyncManager

class BookBase(APICaller, ABC):
    def __init__(self, category: str, book_name: str, redis_database: int, payload_batch: int, async_batch: int,
                 expiration_time: int = 600):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        self.expiration_time = expiration_time # Used for Redis data expiration
        self.redis_database = redis_database # Used for Redis database selection
        self.bettorodds_mapping = BettoroddsMapping(payload_batch=payload_batch, async_batch=async_batch, book_name=book_name)
        self.impersonate = self._get_impersonate(book_name=book_name, category=category)

        super().__init__()

    def _get_impersonate(self, category: str, book_name: str):
        config = BookConfiguration.get_provider(category=category, book_name=book_name)
        return config.curl_impersonation


    @staticmethod
    def generate_key(key_data) -> str | None:
        """Generate a unique key based on the provided data."""
        if not key_data or not isinstance(key_data, list) or None in key_data:
            return None

        generate_key = sorted(key_data, reverse=True)
        return "_".join([str(key.replace(" ", "_")).lower() for key in generate_key])


    @abstractmethod
    async def run_book(self):
        raise NotImplementedError("Subclasses must implement the run_book method.")


    def unique_teams_helper(self, raw_unique_data_passer: list, sportsbook_name: str) -> list[dict]:
        """Helper to build a unique team list from raw data"""
        seen = set()
        team_data = []

        for data in raw_unique_data_passer:
            if any([data.get("future", False), data.get("live", False), data.get("combo", False)]):
                continue

            player_name = data.get("player_name")
            league = data.get("league")
            solo_game = data.get("solo_game", False)

            if solo_game:
                if not player_name or not league:
                    continue

                key = (player_name.lower(), league.lower())
                if key not in seen:
                    seen.add(key)
                    team_data.append({
                        "team_name": player_name.strip(),
                        "league": league,
                        "solo_game": solo_game,
                        "sportsbook": sportsbook_name
                    })

                    continue
            team_a = data.get("team_a")
            team_b = data.get("team_b")

            if not team_a and not team_b:
                continue

            for team in (team_a, team_b):
                if team and team.strip():
                    if not league:
                        continue

                    key = (team.lower(), league.lower())
                    if key not in seen:
                        seen.add(key)
                        team_data.append({
                            "team_name": team.strip(),
                            "league": league,
                            "solo_game": solo_game,
                            "sportsbook": sportsbook_name
                        })

        return team_data

    def add_to_events(self, events: dict, item, game_data_cls):
        """Helper to add sportsbook data to events dictionary grouped by team_key."""
        key = item.game_key

        if key not in events:
            events[key] = game_data_cls(
                game_key=key,
                league=item.league,
                start_date=item.start_date,
                team_data=item.team_data,
                solo_game=item.solo_game,
                odds=[],
            )

        events[key].odds.extend(item.odds)

    def map_data(self, original_sportsbook_data: list, mapped_teams: dict, mapped_players: dict, mapped_markets: dict,
                 solo_game_mapper_func: Optional[Callable] = None):

        for data in original_sportsbook_data:
            solo_game = getattr(data, "solo_game", False)
            if solo_game and solo_game_mapper_func:
                solo_game_mapper_func(
                    stats=data.odds,
                    game_data=data,
                    mapped_players=mapped_players
                )


                continue

            for side in ["team_a", "team_b"]:
                league = data.league
                team_name_attr = getattr(data.team_data, side, None)
                if not team_name_attr:
                    continue

                team_key = f"{team_name_attr.lower()}-{league.lower()}"
                found_team = mapped_teams.get(team_key)
                if found_team:
                    data.league = found_team["league"]
                    setattr(data.team_data, side, found_team["team_name"])
                    setattr(data.team_data, f"{side}_abbreviation", found_team.get("abbreviation"))

                    for stats in data.odds:
                        if getattr(stats, "player_team", None):
                            attr_name = "player_team"
                        elif getattr(stats, "bet_team", None):
                            attr_name = "bet_team"
                        else:
                            continue

                        team_value = getattr(stats, attr_name)

                        if team_value and team_value.lower() == found_team["original_name"].lower():
                            setattr(stats, attr_name, found_team["team_name"])


            data.game_key = self.generate_key(
                [data.team_data.team_a, data.team_data.team_b, data.start_date])

            if data.team_data.team_a and data.team_data.team_b:
                data.event_name = " vs ".join(sorted([data.team_data.team_a, data.team_data.team_b]))

            for stats in data.odds:
                if getattr(stats, "stat_type", None):
                    attr_name = "stat_type"
                elif getattr(stats, "market", None):
                    attr_name = "market"
                else:
                    continue

                stat_value = getattr(stats, attr_name)

                stat_key = f"{stat_value.lower()}-{league.lower()}"

                if stat_key in mapped_markets:
                    setattr(stats, attr_name, mapped_markets[stat_key])


        return original_sportsbook_data

    async def team_look_up(self, team_data: list) -> dict:
        """Look up the teams and return the dict build for players and teams"""
        mapper = FindMapper()
        mapped_teams = await mapper.controller(team_data=team_data)

        def create_key(data: dict) -> str:
            return f'{data["original_name"].lower()}-{data["league"].lower()}'

        def create_build(data: dict) -> dict:
            return {
                **(
                    {"team_name": data.get("team_name")}
                    if not data.get("solo_game")
                    else {
                        "player_name": data.get("team_name")
                    }
                ),
                "league": data.get("league"),
                "original_league": data.get("original_league"),
                "original_name": data.get("original_name"),
                "source": "Internal"
            }

        return {
            "players": {create_key(player): create_build(player) for player in mapped_teams if player.get("solo_game")},
            "teams": {create_key(team): create_build(team) for team in mapped_teams if not team.get("solo_game")},
        }

    @abstractmethod
    async def map_runner(self, sportsbook_data: list, session: aiohttp.ClientSession = None):
        raise NotImplementedError("Subclasses must implement the map_runner method.")

    async def store_data(self, data_to_store: dict | list, database: int, book_name: str):
        if not data_to_store:
            return

        redis_instance = RedisAsyncManager(database=database)

        wrapped_data = {
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "data": data_to_store
        }

        await redis_instance.store_data(
            key_name=f"{book_name}:game",
            data_to_store=data_to_store,
            key_expiration=self.expiration_time
        )

        await redis_instance.store_data(
            key_name=f"{book_name}:base",
            data_to_store=wrapped_data,
            key_expiration=self.expiration_time
        )

    def check_team_in_bettorodds(self, teams: dict, name_to_check: str):
        name_to_check = name_to_check.lower()

        return any(
            name_to_check == mapped.get("original_name", "").lower()
            or name_to_check == mapped.get("team_name", "").lower()
            for mapped in teams.values()
        )

    async def combine_bettorodds_internal_mapping(self, raw_unique_data: list, bettorodds_mapped_data: dict) -> dict:
        bettorodds_teams = bettorodds_mapped_data.get("teams", {})
        bettorodds_players = bettorodds_mapped_data.get("players", {})
        bettorodds_markets = bettorodds_mapped_data.get("markets", {})

        sportsbook_name = self.__class__.__name__
        unique_data = self.unique_teams_helper(raw_unique_data_passer=raw_unique_data,
                                               sportsbook_name=sportsbook_name.lower())

        filtered_unique_data = [
            data
            for data in unique_data
            if not (
                    self.check_team_in_bettorodds(bettorodds_teams, data.get("team_name"))
                    or self.check_team_in_bettorodds(bettorodds_players, data.get("team_name"))
            )
        ]

        internal_mapping = await self.team_look_up(team_data=filtered_unique_data)

        teams = {**internal_mapping.get("teams", {}), **bettorodds_teams}
        players = {**internal_mapping.get("players", {}), **bettorodds_players}

        return {
            "teams": teams,
            "players": players,
            # "teams": bettorodds_teams,
            # "players": bettorodds_players,
            "markets": bettorodds_markets
        }

    @staticmethod
    def return_market_mapper():
        """Returns a dictionary mapping various market period identifiers to standardized keys."""
        return {
            "fg": "Full",
            "1h": "1H",
            "h1": "1H",
            "2h": "2H",
            "h2": "2H",
            "1q": "1Q",
            "q1": "1Q",
            "2q": "2Q",
            "q2": "2Q",
            "3q": "3Q",
            "q3": "3Q",
            "4q": "4Q",
            "q4": "4Q",
        }










