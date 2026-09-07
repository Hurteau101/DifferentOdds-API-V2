from dataclasses import dataclass, field
from typing import Optional, TypedDict
from Utils.helpers import cache_time
from Internal_Mapping.static_mapping import static_mapping
from Books.Bases.book_base import BookBase


def map_teams(name: str | None, league: str) -> tuple:
    """Look up the canonical team name, returning (name, abbreviation)."""
    if not name or not league:
        return name, None, None

    mapped = static_mapping.team_look_up(name, league)
    if isinstance(mapped, dict):
        return mapped.get("normalized_name"), mapped.get("abbreviation"), mapped.get("league")

    return mapped, None, None

class OddsFormat(TypedDict, total=False):
    american_odds: float # Books Using this: (PrizePicks, Underdog, ParlayPlay)
    decimal_odds: float # Books Using this: (PrizePicks, Underdog)

@dataclass
class Stats:
    line: float | None
    bet_type: str | None
    future: bool
    odds_format: Optional[OddsFormat] = field(default=None)
    live: bool = False

@dataclass
class TeamData:
    team_a: str | None
    team_b: str | None
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

@dataclass
class GameData:
    event_name: str = field(init=False)
    league: str
    start_date: str
    game_key_items: list
    team_data: TeamData
    odds: list[Stats]
    game_key: str = field(init=False)
    solo_game: Optional[bool] = None
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

    def __post_init__(self):
        if self.start_date:
            self.start_date = cache_time(self.start_date)

        self.league = static_mapping.league_look_up(self.league)

        team_a, team_a_abbreviation, team_a_league = map_teams(self.team_data.team_a, self.league)

        self.team_a = team_a
        self.team_a_abbreviation = team_a_abbreviation if team_a_abbreviation else self.team_a_abbreviation
        self.league = team_a_league if team_a_league else self.league

        team_b, team_b_abbreviation, team_b_league = map_teams(self.team_data.team_b, self.league)
        self.team_b = team_b
        self.team_b_abbreviation = team_b_abbreviation if team_b_abbreviation else self.team_data.team_b_abbreviation

        # If the team_a league is not set, set it to the team_b league if it exists.
        if not team_a_league:
            self.league = team_b_league if team_b_league else self.league

        mapped_game_keys = []
        for key in self.game_key_items:
            if key:
                team, _, _ = map_teams(key, self.league)
                mapped_game_keys.append(team)

        if not mapped_game_keys:
            # print(f"No mapped game keys found for {self.game_key_items}")
            self.game_key = BookBase.generate_key([self.team_data.team_a, self.team_data.team_b, self.start_date])

        self.game_key = BookBase.generate_key([*mapped_game_keys, self.start_date])

        self.event_name = " vs ".join(sorted([self.team_a, self.team_b])) if self.team_a and self.team_b else "N/A"

