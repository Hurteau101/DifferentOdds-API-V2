from dataclasses import dataclass, field, InitVar
from typing import Optional, TypedDict
from Utils.helpers import clean_structure, cache_time
from Internal_Mapping.static_mapping import static_mapping


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
class GameData:
    event_name: str = field(init=False)
    league: str
    start_date: str
    game_key: str
    team_a: str | None
    team_b: str | None
    odds: list[Stats]
    solo_game: Optional[bool] = None
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

    def __post_init__(self):
        if self.start_date:
            self.start_date = cache_time(self.start_date)

        self.league = static_mapping.league_look_up(self.league)

        team_a, team_a_abbreviation, team_a_league = map_teams(self.team_a, self.league)

        self.team_a = team_a
        self.team_a_abbreviation = team_a_abbreviation if team_a_abbreviation else self.team_a_abbreviation
        self.league = team_a_league if team_a_league else self.league

        team_b, team_b_abbreviation, team_b_league = map_teams(self.team_b, self.league)
        self.team_b = team_b
        self.team_b_abbreviation = team_b_abbreviation if team_b_abbreviation else self.team_b_abbreviation

        # If the team_a league is not set, set it to the team_b league if it exists.
        if not team_a_league:
            self.league = team_b_league if team_b_league else self.league

        self.event_name = " vs ".join(sorted([self.team_a, self.team_b])) if self.team_a and self.team_b else "N/A"

