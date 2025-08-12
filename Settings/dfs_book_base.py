import inspect
import re
from abc import ABC

import unicodedata

from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig
from Settings.logger import FileLogger, ConsoleLogger
import os
from  Settings.dfs_model import PlayerData
from Mapper.mapping_database import Mapper
from Mapper.static_mapper import LEAGUES, STAT_TYPES

class DFSBookBase(BookBase, ABC):
    """Base class for DFS books, inheriting from BookBase."""
    def __init__(self, request_type, sportsbook_name: str, log_directory="DFS Logs", log_name=None):
        self.book_data = SportsbookConfig.get_dfs_provider(sportsbook_name)
        super().__init__(request_type, log_directory=log_directory, log_name=log_name)
        self.mapper = Mapper()
        self.LEAGUE_MAPPING = LEAGUES
        self.STAT_TYPES = STAT_TYPES


    def _unique_teams(self, sportsbook_data: list[PlayerData], sportsbook):
        """Create a list of unique team names, so we can pass this data to RapidFuzz and OpenAI"""


        team_set = set()
        team_data = []

        for data in sportsbook_data:
            if data.future or data.combo or data.live:
                continue

            player_name = data.player_name
            league = data.league
            team_a = data.team_data.team_a
            team_b = data.team_data.team_b

            # Some solo games like Tennis on some books will have team_a and team_b, so we need this check.
            if data.solo_game and (not data.team_data.team_a or not data.team_data.team_b):
                key = (player_name, league)
                if key not in team_set:
                    team_set.add(key)
                    team_data.append({
                        "team_name": player_name.strip(),
                        "league": league,
                        "solo_game": data.solo_game,
                        "sportsbook": sportsbook
                    })
            else:
                for team in (team_a, team_b):
                    if team and team.strip():
                        key = (team, league)
                        if key not in team_set:
                            team_set.add(key)
                            team_data.append({
                                "team_name": team.strip(),
                                "league": league,
                                "solo_game": data.solo_game,
                                "sportsbook": sportsbook
                            })
        return team_data

    @staticmethod
    def clean_and_normalize_name(name):
        if name is not None:
            if name.islower():
                name.title()

            if name.endswith('…'):
                name = name[:-1]

            nfkd_form = unicodedata.normalize('NFD', name)
            # Filter out accent characters (mark category)
            name = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])

        return name

    async def _database_mapper(self, sportsbook_data: list[PlayerData]):
        sportsbook = self.__class__.__name__
        unique_data = self._unique_teams(sportsbook_data, sportsbook.lower())
        mapped_teams = await self.mapper.controller(unique_data)

        # Create a map of the returned RapidFuzz + OpenAI mapping.
        team_lookup = {
            team["original_name"].lower(): team
            for team in mapped_teams
        }

        # Loop through the original data and map it to the new mapped data set.
        for data in sportsbook_data:
            if data.future:
                continue

            if data.solo_game and (not data.team_data.team_a or not data.team_data.team_b):
                team = team_lookup.get(data.player_name.lower())
                if team:
                    data.league = team["league"]
                    data.player_team = team["team_name"]
                    self._generate_key([data.player_name, data.start_date])
            else:
                for side in ['team_a', 'team_b']:
                    team_name_attr = getattr(data.team_data, side)
                    team = team_lookup.get(team_name_attr.lower())
                    if team:
                        data.league = team["league"]
                        setattr(data.team_data, side, team["team_name"])
                        setattr(data.team_data, f"{side}_abbreviation", team.get("abbreviation"))

                data.team_data.team_key = self._generate_key([data.team_data.team_a, data.team_data.team_b, data.start_date])

        return sportsbook_data
