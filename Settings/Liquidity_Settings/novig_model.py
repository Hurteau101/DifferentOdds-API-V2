from dataclasses import dataclass
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
from pydantic import dataclasses as pydantic_dataclasses

# @dataclass
# class Order:
#     outcome_id: str
#     qty: float
#     decimal_price: float
#     original_qty: float
#     created_at: str
#     price: float
#     american_price: float
#     total_win: float
#     total_risk: float
#     liquidity_left: float
#
# @dataclass
# class OutcomeSide:
#     orders: list[Order]
#     total_liquidity: float
#     highest_order: Order
#
# @pydantic_dataclasses.dataclass
# class Game:
#     league: Optional[str] = None
#     event: Optional[str] = None
#     start_date: Optional[str] = None
#     market_type: Optional[str] = None
#     outcomes: dict[str, list[OutcomeSide]] = None
#     liquidity_difference: Optional[float] = None
#     player: Optional[str] = None
#     line: Optional[float] = None


@pydantic_dataclasses.dataclass
class Order:
    outcome_id: str
    qty: float
    decimal_price: float
    original_qty: float
    created_at: str
    price: float
    american_price: float
    total_win: float
    total_risk: float
    liquidity_left: float

@pydantic_dataclasses.dataclass
class OutcomeSide:
    orders: list[Order]
    total_liquidity: float
    highest_order: Order

@pydantic_dataclasses.dataclass
class Game:
    league: Optional[str] = None
    event: Optional[str] = None
    start_date: Optional[str] = None
    market_type: Optional[str] = None
    outcomes: dict[str, list[OutcomeSide]] = None
    liquidity_difference: Optional[float] = None
    player: Optional[str] = None
    line: Optional[float] = None
    fetched_time: Optional[str] = None
    book_name: str = "Novig"

class BookDataLiquidity(BaseModel):
    last_refresh: str | datetime | int
    data: list[Game]