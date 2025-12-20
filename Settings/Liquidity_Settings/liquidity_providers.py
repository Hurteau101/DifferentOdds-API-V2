from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class LiquidityProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    active: Optional[bool] = False


LIQUIDITY_PROVIDERS = [
    LiquidityProvider(
        title="Novig",
        name="novig",
        url={
            "base_url": "https://gql.novig.us/v1/graphql",
            "league_url": "https://api.novig.us/recs/v1/tabs/rankings"
        },
        method="POST",
        headers={
            "Content-Type": "application/json"
        },
        active=True
    ),
]