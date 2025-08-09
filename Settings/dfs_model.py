from dataclasses import dataclass, field
from typing import Dict, List, Optional, TypedDict

class Odds(TypedDict, total=False):
    american_odds: float # Books Using this: (PrizePicks, Underdog, ParlayPlay)
    decimal_odds: float # Books Using this: (PrizePicks, Underdog)
    boosted_payout: bool # Books Using this: (ParlayPlay)
    boosted_expiry: str # Books Using this: (ParlayPlay)

class OptionalStatInformation(TypedDict, total=False):
    odds_type: str # The type of odds (Standard, Demon, etc) | Books Using this: (PrizePicks, Underdog)
    market_type: str # The type of market (Full, Half, etc) | Books Using this: (PrizePicks | Underdog, ParlayPlay)
    betlink: Dict[str, str] # Books Using this: (PrizePicks)
    multiplier: float
    odds: Odds

class Discounts(TypedDict, total=False):
    discount_name : str # Books Using this: (PrizePicks, Ownerbox)
    discount_percentage: str # Books Using this: (PrizePicks, Ownerbox)
    discount_expiry: str # Books Using this: (Ownerbox)


@dataclass
class Stats:
    stat_type: str
    line: float
    bet_direction: str # The type of bet (Over, Under)
    regular_line: bool # If the bet is just a regular line (no multiplier)
    optional_stats: OptionalStatInformation = field(default_factory=OptionalStatInformation)
    discounts: Optional[Discounts] = field(default_factory=Discounts)


@dataclass
class TeamData:
    team_a: str
    team_b: str
    team_key: str
    player_team: str
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

@dataclass
class PlayerData:
    player_name: str
    league: str
    start_date: str
    team_data: TeamData
    future: bool
    stats: List[Stats]
    solo_game: Optional[bool] = None


