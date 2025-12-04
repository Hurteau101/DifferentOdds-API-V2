from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class Markets:
    market: str
    american_odds: float
    bet_team: Optional[str] = None
    bet_type: Optional[str] = None
    line: Optional[str] = None
    bet_player: Optional[str] = None


@dataclass
class TeamData:
    team_a: str
    team_b: str
    team_key: str
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None


@dataclass
class GameData:
    book_name: str
    start_date: str
    league: str
    team_data: TeamData
    event_name: str
    odds: list[Markets]
    future: bool = False
    solo_game: bool = None
    # TESTING BELOW
    league_id: Optional[str] = None
    raw_league_name: Optional[str] = None