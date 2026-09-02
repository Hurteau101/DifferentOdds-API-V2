from dataclasses import dataclass, field, InitVar
from typing import Optional, ClassVar
from Settings.Models.base_models import Stats, OddsFormat
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

    def __post_init__(self, static_mapping: dict):
        super().__post_init__(static_mapping)
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        self.market = static_mapping.get("static_mapping", {}).get(self.market.lower(), self.market)