from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


@dataclass
class Order:
    liquidity: float
    american_odds: float | int
    market: str
    bet_info: str
    is_best: Optional[bool] = None
    price: Optional[float] = None
    line: Optional[float] = None
    player: Optional[str] = None
    player_team: Optional[str] = None


@dataclass
class Game:
    key: str
    event: str
    start_date: str
    league: str
    team_1: Optional[str] = None
    team_1_abbreviation: Optional[str] = None
    team_2: Optional[str] = None
    team_2_abbreviation: Optional[str] = None
    orders: list[Order] = None


class BookDataPrediction(BaseModel):
    last_refresh: str | datetime | int
    data: list[Game]