from dataclasses import dataclass, field, fields
from typing import Optional, TypedDict, Dict
from Redis.redis_manager import static_mapping_service
from Utils.helpers import clean_structure, cache_time

def get_static_mapping():
    return static_mapping_service.get()

### Testing Version
class Discounts(TypedDict, total=False):
    discount_name : str # Books Using this: (PrizePicks, Ownerbox)
    discount_percentage: str # Books Using this: (PrizePicks, Ownerbox)
    discount_expiry: str # Books Using this: (Ownerbox)


class OddsFormat(TypedDict, total=False):
    american_odds: float # Books Using this: (PrizePicks, Underdog, ParlayPlay)
    decimal_odds: float # Books Using this: (PrizePicks, Underdog)


class OptionalStatInformation(TypedDict, total=False):
    odds_type: str # The type of odds (Standard, Demon, etc) | Books Using this: (PrizePicks, Underdog)
    market_type: str # The type of market (Full, Half, etc) | Books Using this: (PrizePicks | Underdog, ParlayPlay)
    betlink: Dict[str, str] # Books Using this: (PrizePicks)
    multiplier: float
    odds_format: OddsFormat
    internal_id: str # Books Using this: (Fanduel_Picks)
    boosted_payout: bool # Books Using this: (ParlayPlay) ## CHECK THESE
    boosted_expiry: str # Books Using this: (ParlayPlay) ## CHECK THESE

@dataclass
class Stats:
    player_name: str
    player_team: str
    stat_type: str
    line: float
    bet_type: str
    regular_line: bool
    combo: Optional[bool] = False
    live: Optional[bool] = False
    optional_stats: Optional[OptionalStatInformation] = field(default_factory=OptionalStatInformation)
    discounts: Optional[Discounts] = field(default_factory=Discounts)

    def __post_init__(self):
        modified_stat_type = self.stat_type.replace("Player ", "").lower()
        self.stat_type = get_static_mapping().get("stats").get(modified_stat_type, modified_stat_type.title())
        self.player_name = clean_structure(self.player_name)
        self.player_team = clean_structure(self.player_team)


@dataclass
class TeamData:
    team_a: str
    team_b: str
    team_a_abbreviation: Optional[str] = None
    team_b_abbreviation: Optional[str] = None

    def __post_init__(self):
        self.team_a = clean_structure(self.team_a)
        self.team_b = clean_structure(self.team_b)

@dataclass
class GameData:
    event_name: str = field(init=False)
    league: str
    start_date: str
    game_key: str
    future: bool
    team_data: TeamData
    odds: list[Stats]
    solo_game: Optional[bool] = None

    def __post_init__(self):
        self.league = get_static_mapping().get("leagues").get(self.league.lower(), self.league.upper())
        self.start_date = cache_time(self.start_date)

        # Work on a better solution.
        if not self.solo_game or all([self.team_data.team_a, self.team_data.team_b]):
            self.event_name = " vs ".join(sorted([self.team_data.team_a, self.team_data.team_b]))
        else:
            self.event_name = "N/A"


#### Working Version
# class Discounts(TypedDict, total=False):
#     discount_name : str # Books Using this: (PrizePicks, Ownerbox)
#     discount_percentage: str # Books Using this: (PrizePicks, Ownerbox)
#     discount_expiry: str # Books Using this: (Ownerbox)
#
#
# class Odds(TypedDict, total=False):
#     american_odds: float # Books Using this: (PrizePicks, Underdog, ParlayPlay)
#     decimal_odds: float # Books Using this: (PrizePicks, Underdog)
#     boosted_payout: bool # Books Using this: (ParlayPlay)
#     boosted_expiry: str # Books Using this: (ParlayPlay)
#
# class OptionalStatInformation(TypedDict, total=False):
#     odds_type: str # The type of odds (Standard, Demon, etc) | Books Using this: (PrizePicks, Underdog)
#     market_type: str # The type of market (Full, Half, etc) | Books Using this: (PrizePicks | Underdog, ParlayPlay)
#     betlink: Dict[str, str] # Books Using this: (PrizePicks)
#     multiplier: float
#     odds: Odds
#     internal_id: str # Books Using this: (Fanduel_Picks)
#
# @dataclass
# class Stats:
#     stat_type: str
#     line: float
#     bet_direction: str
#     regular_line: bool
#     optional_stats: Optional[OptionalStatInformation] = field(default_factory=OptionalStatInformation)
#     discounts: Optional[Discounts] = field(default_factory=Discounts)
#
#     def __post_init__(self):
#         self.stat_type = get_static_mapping().get("stats").get(self.stat_type.lower(), self.stat_type)
#
#
# @dataclass
# class TeamData:
#     team_a: str
#     team_b: str
#     team_key: str # Typically [team_a_team_b_league_date]
#     player_team: str
#     team_a_abbreviation: Optional[str] = None
#     team_b_abbreviation: Optional[str] = None
#
#     def __post_init__(self):
#         self.team_a = clean_structure(self.team_a)
#         self.team_b = clean_structure(self.team_b)
#         self.player_team = clean_structure(self.player_team)
#
#
# @dataclass
# class GameData:
#     league: str
#     start_date: str
#     future: bool
#     player_name: str
#     team_data: TeamData
#     stats: list[Stats]
#     solo_game: Optional[bool] = None
#     combo: Optional[bool] = False
#     live: Optional[bool] = False
#
#     def __post_init__(self):
#         self.league = get_static_mapping().get("leagues").get(self.league.lower(), self.league)
#         self.player_name = clean_structure(self.player_name)
#         self.start_date = cache_time(self.start_date)

