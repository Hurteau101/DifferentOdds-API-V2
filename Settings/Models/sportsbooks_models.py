import re
from dataclasses import dataclass
from typing import Optional

from Settings.Models.base_models import Stats, get_static_mapping
from Utils.helpers import clean_structure


def ordinal_formatter(market_name):
    """Format the string if it is an ordinal market, otherwise return the original string."""
    pattern = r'\b\d+(st|nd|rd|th)\b'
    result = re.sub(pattern, lambda m: m.group(0), market_name, flags=re.IGNORECASE)

    if re.search(pattern, market_name, flags=re.IGNORECASE):
        result_split = result.split()

        return f"{result_split[0]} {' '.join(result_split[1:]).title()}"

    return market_name.title()

# Use kw_only - As inheritance restriction.
@dataclass(kw_only=True)
class SportsbookStats(Stats):
    market: str
    bet_team: Optional[str] = None
    bet_player: Optional[str] = None

    def __post_init__(self):
        self.bet_player = clean_structure(self.bet_player)
        self.bet_team = clean_structure(self.bet_team)
        self.market = get_static_mapping().get("stats").get(self.market.lower(), ordinal_formatter(self.market.lower()) if self.market else self.market)
