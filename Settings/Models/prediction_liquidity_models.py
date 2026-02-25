from dataclasses import dataclass, field
from typing import Optional, ClassVar, List

from Settings.Models.base_models import Stats, get_static_mapping, OddsFormat
from Utils.helpers import clean_structure

@dataclass
class LiquidityData:
    odds_format: OddsFormat
    liquidity: float
    price: Optional[float] = None
    is_best: Optional[bool] = None
    additional_information: dict = field(default_factory=dict)


@dataclass(kw_only=True)
class PredictionLiquidityStats(Stats):
    odds_format: ClassVar[Optional[OddsFormat]] = None # Removes odds format.

    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None
    player_team: Optional[str] = None
    liquidity_data: list[LiquidityData]

    def __post_init__(self):
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        self.market = get_static_mapping().get("stats").get(self.market, self.market.title() if self.market else self.market)