from dataclasses import dataclass, field, InitVar
from typing import Optional, ClassVar
from Settings.Models.base_models import Stats, OddsFormat, map_teams
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
    league: InitVar[str]
    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None
    player_team: Optional[str] = None
    liquidity_data: list[LiquidityData]

    def __post_init__(self, league: str):
        self.bet_player = clean_structure(self.bet_player)
        player_team, _, _ = map_teams(self.player_team, league)
        self.player_team = player_team