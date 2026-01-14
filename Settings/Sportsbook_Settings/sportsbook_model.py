from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel


@dataclass
class Markets:
    market: str
    american_odds: float
    bet_team: Optional[str] = None
    bet_type: Optional[str] = None
    line: Optional[str] = None
    bet_player: Optional[str] = None
    future: bool = False


@dataclass
class TeamData:
    team_key: str
    team_a: Optional[str] = None
    team_b: Optional[str] = None
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
    # solo_game: bool = None

class BookDataSportsbook(BaseModel):
    last_refresh: str | datetime | int
    data: list[GameData]