from typing import TypedDict, Dict, Optional
from Settings.Models.base_models import Stats, get_static_mapping
from dataclasses import dataclass, field



class Discounts(TypedDict, total=False):
    discount_name : str # Books Using this: (PrizePicks, Ownerbox)
    discount_percentage: str # Books Using this: (PrizePicks, Ownerbox)
    discount_expiry: str # Books Using this: (Ownerbox)


class OptionalStatInformation(TypedDict, total=False):
    odds_type: str # The type of odds (Standard, Demon, etc) | Books Using this: (PrizePicks, Underdog)
    market_type: str # The type of market (Full, Half, etc) | Books Using this: (PrizePicks | Underdog, ParlayPlay)
    betlink: Dict[str, str] # Books Using this: (PrizePicks)
    multiplier: float
    internal_id: str # Books Using this: (Fanduel_Picks)
    boosted_payout: bool # Books Using this: (ParlayPlay) ## CHECK THESE
    boosted_expiry: str # Books Using this: (ParlayPlay) ## CHECK THESE

# Use kw_only - As inheritance restriction.
@dataclass(kw_only=True)
class DFSStats(Stats):
    player_name: str
    player_team: str
    stat_type: str
    regular_line: bool
    optional_stats: OptionalStatInformation = field(default_factory=dict)
    discounts: Discounts = field(default_factory=dict)
    combo: Optional[bool] = False

    def __post_init__(self):
        modified_stat_type = self.stat_type.replace("Player ", "").lower()
        self.stat_type = get_static_mapping().get("stats").get(modified_stat_type, modified_stat_type.title())