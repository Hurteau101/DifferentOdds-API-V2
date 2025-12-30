from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


@dataclass
class Order:
    price: float
    liquidity: float
    american_odds: float | int
    is_best: bool
    market: str
    bet_info: str
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
    team_2: Optional[str] = None
    orders: list[Order] = None


class BookDataPrediction(BaseModel):
    last_refresh: str | datetime | int
    data: list[Game]