from typing import TypedDict, Dict, Optional
from Settings.Models.base_models import Stats, map_teams
from dataclasses import dataclass, field, InitVar
from Books.Bases.mapper_base import MapperBase
from Utils.helpers import clean_structure
from Internal_Mapping.static_mapping import static_mapping

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
    league: InitVar[str]
    player_name: str
    player_team: str
    stat_type: str
    regular_line: bool
    optional_stats: OptionalStatInformation = field(default_factory=dict)
    discounts: Discounts = field(default_factory=dict)
    combo: Optional[bool] = False
    prop_key: Optional[str] = field(default=None)

    def __post_init__(self, league: str):
        self.player_name = clean_structure(self.player_name)

        player_team, _, _ = map_teams(self.player_team, league)
        self.player_team = player_team

        if self.stat_type:
            self.stat_type = self.stat_type.lower().replace("player", '')

        self.stat_type = static_mapping.stat_look_up(self.stat_type)

        self.prop_key = MapperBase.build_prop_key(
            stat=f"Player {self.stat_type}",
            side=self.bet_type,
            line=str(self.line),
            player=self.player_name,
        )
