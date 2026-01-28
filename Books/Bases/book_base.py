from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Callable
from Database.find_mapping import FindMapper
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import SportbookRequestType, APICaller
from Redis.redis_manager import RedisAsyncManager

class BookBase(APICaller, ABC):
    def __init__(self, category: str, book_name: str, request_type: SportbookRequestType, redis_database: int,
                 expiration_time: int = 600):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        self.expiration_time = expiration_time # Used for Redis data expiration
        self.redis_database = redis_database # Used for Redis database selection
        super().__init__(request_type=request_type)

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
        """Helper to build a unique team list from raw data passed from external_mapper"""
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


    def map_helper(self, sportsbook_data: list, mapped_teams: dict, solo_game_mapper_func: Optional[Callable] = None,
                   player_team_mapper_func: Optional[Callable] = None) -> list:
        """
        Helper to map sportsbook data with found teams from Redis/Database.

        There are 3 optional function caller parameters, due to different dataclass models, and where each attribute
        is located. Passing the functions to map those specific attributes allows for more flexibility.

        :param sportsbook_data: List of sportsbook dataclasses.
        :param mapped_teams: Dictionary of mapped teams.
        :param solo_game_mapper_func: Optional function to map solo games.
        :param player_team_mapper_func: Optional function to map player team.
        :param stat_mapper_func: Optional function to map stat_types.

        :return: Mapped sportsbook data.
        """
        for data in sportsbook_data:
            solo_game = getattr(data, "solo_game", False)
            if solo_game and solo_game_mapper_func:
                for stats in data.odds:
                    solo_game_mapper_func(stats, data, mapped_teams)
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

                    if player_team_mapper_func:
                        for stats in data.odds:
                            player_team_mapper_func(stats, found_team)

            data.game_key = self.generate_key(
                [data.team_data.team_a, data.team_data.team_b, data.start_date])

            data.event_name = " vs ".join(sorted([data.team_data.team_a, data.team_data.team_b]))


        return sportsbook_data


    async def team_look_up(self, raw_unique_data: list, sportsbook_name: str) -> dict:
        unique_data = self.unique_teams_helper(raw_unique_data_passer=raw_unique_data, sportsbook_name=sportsbook_name.lower())
        mapper = FindMapper()
        mapped_teams = await mapper.controller(team_data=unique_data)

        return {
            f'{team["original_name"].lower()}-{team["league"].lower()}': team
            for team in mapped_teams
        }

    @abstractmethod
    async def external_mapper(self, sportsbook_data: list):
        raise NotImplementedError("Subclasses must implement the external_mapper method.")

    async def store_data(self, data_to_store: dict, database: int, book_name: str):
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










