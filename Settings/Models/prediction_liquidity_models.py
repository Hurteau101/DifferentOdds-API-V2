from dataclasses import dataclass, field
from typing import Optional, ClassVar, List

from Settings.Models.base_models import Stats, get_static_mapping, OddsFormat
from Utils.helpers import clean_structure

# def create_liquidity_key(line: str | float | int, bet_type: str, bet_team: str, bet_player: str, market: str):
#     if not line:
#         line = "-"
#
#     if not bet_type:
#         bet_type = "-"
#
#     if not bet_team:
#         bet_team = "-"
#
#     if not bet_player:
#         bet_player = "-"
#
#     return f"{market}_{line}_{bet_type}_{bet_team}_{bet_player}".lower()
#

# @dataclass(frozen=True)
# class SelectionKey:
#     market: str
#     line: Optional[float]
#     side: Optional[str]
#     team: Optional[str]
#     player: Optional[str]


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
    # selection_key: SelectionKey = field(init=False)

    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None
    player_team: Optional[str] = None
    liquidity_data: list[LiquidityData]

    def __post_init__(self):
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        self.market = get_static_mapping().get("stats").get(self.market.lower(), self.market.title() if self.market else self.market)

        #
        # self.selection_key = SelectionKey(
        #     market=self.market,
        #     line=self.line,
        #     side=self.bet_type,
        #     team=self.bet_team,
        #     player=self.bet_player,
        # )