from dataclasses import dataclass
from typing import Optional
from Settings.Models.base_models import Stats
from Utils.helpers import clean_structure, ordinal_formatter


# Use kw_only - As inheritance restriction.
@dataclass(kw_only=True)
class SportsbookStats(Stats):
    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None

    def __post_init__(self, static_mapping: dict):
        super().__post_init__(static_mapping)
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        if self.market:
            static_market_name = static_mapping.get("static_mapping", {}).get(self.market.lower(), self.market)
            self.market = ordinal_formatter(static_market_name)