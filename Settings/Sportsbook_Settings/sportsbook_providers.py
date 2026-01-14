from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class SportsbookProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    active: Optional[bool] = False


SPORTSBOOK_PROVIDERS = [
    SportsbookProvider(
        title="Bet105",
        name="bet105",
        url={
            # Mappers URLS
            "sportsbooks": "https://api.kibl.io/sports/get/reference/sportsbooks",
            "leagues": "https://api.kibl.io/sports/get/reference/leagues",
            "segments": "https://api.kibl.io/sports/get/reference/segments",
            "sides": "https://api.kibl.io/sports/get/reference/sides",
            "market_genre": "https://api.kibl.io/sports/get/reference/market-genres",
            "market_status": "https://api.kibl.io/sports/get/reference/market-statuses",
            "market_types": "https://api.kibl.io/sports/get/reference/market-types",
            "fixture_types": "https://api.kibl.io/sports/get/reference/fixture-types",
            "fixtures": "https://api.kibl.io/sports/get/info/fixtures",
            "events": "https://api.kibl.io/sports/get/mapping/fixtures",
            "markets": "https://api.kibl.io/sports/get/info/markets",
        },
        method="GET",
        headers={
            "Accept": "application/json",
        },
        active=True
    ),
]