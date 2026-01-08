import os
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from orjson import orjson

from Redis.redis_manager import RedisSync
from Settings.book_base import BookBase
from abc import ABC
from Settings.sportsbook_config import SportsbookConfig
from Mapper.mapper import Mapper

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

class PredictionBookBase(BookBase, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory=None, log_name=None):
        self.book_data = SportsbookConfig.get_prediction_provider(sportsbook_name)
        self.redis_db = 1

        self.mapper = Mapper()

        if log_directory is None:
            log_directory = os.path.join(PROJECT_ROOT, "Prediction", "Prediction Logs")

        os.makedirs(log_directory, exist_ok=True)

        super().__init__(request_type, log_directory=log_directory, log_name=log_name)

    def check_api_response(self, sportsbook: str, results: list):
        pass


    def _extract_teams(self, sportsbook_data: list, sportsbook_name: str) -> list:
        return [
            {
                "team_name": team,
                "league": sportsbook.league,
                "solo_game": False,
                "sportsbook": sportsbook_name,
            }

            for sportsbook in sportsbook_data
            for team in (sportsbook.team_1, sportsbook.team_2)
        ]

    def _special_date_mapper(self, market_data, mapped_data):
        """Used when a prediction market doesn't offer valid game dates"""
        if not mapped_data:
            return

        game_key = " vs ".join(sorted([
            market_data.team_1,
            market_data.team_2
        ])).replace(" ", "_")

        raw_date = datetime.strptime(market_data.start_date, "%Y-%m-%d")

        # Create key list, since books like Kalshi don't give any indication of the timezone, nor do they provide
        # any times, to switch the timezone to UTC. This should cover those cases.
        key_list = [
            f"{game_key}_{market_data.league}_{(raw_date + timedelta(days=i)).date()}".lower()
            for i in range(0, 2)
        ]

        matched_key_date = next((
            mapped_data.get(key)
            for key in key_list
            if key in mapped_data
        ), None)

        if matched_key_date:
            market_data.start_date = self.cache_time(matched_key_date)
        else:
            modified_date = datetime.strptime(market_data.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            market_data.start_date = self.cache_time(modified_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

    async def _database_mapper(self, sportsbook_data: list):
        sportsbook = self.__class__.__name__
        teams = self._extract_teams(sportsbook_data, sportsbook)
        mapped_teams = await self.mapper.controller(teams)
        team_lookup = {
            f'{team["original_name"].lower()}-{team["league"]}': team
            for team in mapped_teams
        }


        special_date_mapper_books = ["kalshi"]
        if sportsbook.lower() in special_date_mapper_books:
            redis = RedisSync(db=2)
            games_data = redis.get("espn_games")
            if games_data:
                mapped_dates = orjson.loads(games_data)


        for data in sportsbook_data:
            for team_selector in ["team_1", "team_2"]:
                original_league = data.league
                team_name_attr = getattr(data, team_selector)
                if not team_name_attr:
                    continue

                team_key = f"{team_name_attr.lower()}-{original_league}"
                team = team_lookup.get(team_key)
                if team:
                    for order in data.orders:
                        original_team = team.get("original_name") or ""
                        if order.bet_team and original_team and original_team.lower() in order.bet_team.lower():
                            order.bet_team = re.sub(
                                re.escape(original_team),
                                team["team_name"],
                                order.bet_team,
                                flags=re.IGNORECASE
                            )

                        # if order.player_team and original_team and original_team.lower() in order.player_team.lower():
                        #     order.player_team = re.sub(
                        #         re.escape(original_team),
                        #         team["team_name"],
                        #         order.player_team,
                        #         flags=re.IGNORECASE
                        #     )

                    data.league = team["league"]
                    setattr(data, team_selector, team["team_name"])


            if sportsbook.lower() in special_date_mapper_books:
                self._special_date_mapper(market_data=data, mapped_data=mapped_dates)

            teams = sorted([data.team_1, data.team_2])
            data.event = f" vs ".join(sorted(teams))
            data.key = self._generate_key([data.event, data.league, data.start_date])


        return sportsbook_data



