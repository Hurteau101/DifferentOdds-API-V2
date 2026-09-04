from dataclasses import dataclass, InitVar
from typing import Optional

from Internal_Mapping.static_mapping import static_mapping
from Settings.Models.base_models import Stats, map_teams
from Utils.helpers import clean_structure


# Use kw_only - As inheritance restriction.
@dataclass(kw_only=True)
class SportsbookStats(Stats):
    league: InitVar[str]
    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None

    def __post_init__(self, league: str):
        self.bet_player = clean_structure(self.bet_player)
        self.market = static_mapping.stat_look_up(self.market)
        bet_team, _, _ = map_teams(self.bet_team, league)
        self.bet_team = bet_team