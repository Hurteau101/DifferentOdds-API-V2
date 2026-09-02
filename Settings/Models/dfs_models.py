from typing import TypedDict, Dict, Optional
from Settings.Models.base_models import Stats
from dataclasses import dataclass, field
from Books.Bases.mapper_base import MapperBase


from Utils.helpers import clean_structure


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
    player_id: str | int
    group_id: str


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
    prop_key: Optional[str] = field(default=None)

    def __post_init__(self, static_mapping: dict):
        super().__post_init__(static_mapping)
        self.player_name = clean_structure(self.player_name)
        self.player_team = clean_structure(self.player_team)
        modified_stat_type = self.stat_type.replace("Player ", "").lower()
        if modified_stat_type:
            self.stat_type = static_mapping.get("static_mapping", {}).get(modified_stat_type, modified_stat_type)
            self.prop_key = MapperBase.build_prop_key(
                stat=f"Player {self.stat_type}",
                side=self.bet_type,
                line=str(self.line),
                player=self.player_name,
            )
