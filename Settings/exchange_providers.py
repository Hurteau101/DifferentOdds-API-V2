from dataclasses import dataclass


@dataclass
class ExchangeProvider:
    title: str
    name: str
    url: dict
    method: str


EXCHANGE_PROVIDERS = [
    ExchangeProvider(
        title="Kalashi",
        name="kalashi",
        url={
            "sports_url": "https://api.elections.kalshi.com/trade-api/v2/series?",
            "markets_url": "https://api.elections.kalshi.com/trade-api/v2/markets?",
            "title_url": "https://api.elections.kalshi.com/trade-api/v2/events?"
        },
        method="GET",
    )
]