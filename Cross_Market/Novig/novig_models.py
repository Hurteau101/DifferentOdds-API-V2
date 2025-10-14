from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class GameDetails:
    game_title: str
    game_start_time: str
    bettor_odds_key: Optional[str] = None


@dataclass
class LiquidityData:
    total_liquidity: float
    total_cost_avg: float


@dataclass
class Orders:
    outcome_id: str
    qty: float
    decimal_price: float
    original_qty: float
    created_at: str
    american_price: float
    total_win: float
    total_risk: float
    liquidity_left: float

@dataclass
class LiquidityData:
    highest_order: Dict


@dataclass
class Player:
    player_name: str
    league: str
    key_name: str
    stat_type: str
    bet_info: str
    line: float
    orders: List[Orders]
    liquidity_data: LiquidityData
    game_details: GameDetails



from pydantic import BaseModel

class FilteredData(BaseModel):
    raw_name: str
    display_name: str
    active: bool

class FilterList(BaseModel):
    filter_data: Dict[str, List[FilteredData]]

    def get_leagues(self) -> List[str]:
        """Get all available leagues"""
        return list(self.filter_data.keys())
