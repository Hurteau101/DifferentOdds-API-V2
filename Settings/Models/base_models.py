from dataclasses import dataclass, field, InitVar
from typing import Optional, TypedDict
from Utils.helpers import clean_structure, cache_time

class OddsFormat(TypedDict, total=False):
    american_odds: float # Books Using this: (PrizePicks, Underdog, ParlayPlay)
    decimal_odds: float # Books Using this: (PrizePicks, Underdog)

@dataclass
class Stats:
    static_mapping: InitVar[dict]
    line: float | None
    bet_type: str | None
    future: bool
    odds_format: Optional[OddsFormat] = field(default=None)
    live: bool = False

    def __post_init__(self, static_mapping: dict):
        if self.bet_type:
            self.bet_type = static_mapping.get("static_mapping", {}).get(self.bet_type.lower(), self.bet_type)


@dataclass
class TeamData:
    team_a: str | None
    team_b: str | None
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

    def __post_init__(self):
        self.team_a = clean_structure(self.team_a)
        self.team_b = clean_structure(self.team_b)

@dataclass
class GameData:
    event_name: str = field(init=False)
    league: str
    start_date: str
    game_key: str
    team_data: TeamData
    odds: list[Stats]
    solo_game: Optional[bool] = None

    def __post_init__(self):
        self.start_date = cache_time(self.start_date)

        # Work on a better solution.
        if self.solo_game or not all([self.team_data.team_a, self.team_data.team_b]):
            temp_key = self.game_key
            if not temp_key:
                self.event_name = "N/A"
            else:
                # Remove the date portion.
                split_key = temp_key.split("_")[:-1]
                self.event_name = " ".join(split_key).replace("_", " ").strip()

            # self.event_name = self.game_key.replace("_", " ") if self.game_key else "N/A"
        elif self.team_data.team_a and self.team_data.team_b:
            self.event_name = " vs ".join(sorted([self.team_data.team_a, self.team_data.team_b]))
            self.event_name = clean_structure(self.event_name)
        else:
            self.event_name = "N/A"

