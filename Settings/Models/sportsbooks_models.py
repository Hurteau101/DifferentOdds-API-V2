from dataclasses import dataclass
from typing import Optional

from Settings.Models.base_models import Stats, get_static_mapping
from Utils.helpers import clean_structure


# Use kw_only - As inheritance restriction.
@dataclass(kw_only=True)
class SportsbookStats(Stats):
    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None

    def __post_init__(self):
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        self.market = get_static_mapping().get("stats").get(self.market, self.market.title() if self.market else self.market)