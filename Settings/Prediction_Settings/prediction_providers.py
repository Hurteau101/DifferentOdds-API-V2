from dataclasses import dataclass


@dataclass
class PredictionProvider:
    title: str
    name: str
    url: dict
    method: str
    active: bool


PREDICTION_PROVIDERS = [
    PredictionProvider(
        title="Kalshi",
        name="kalshi",
        url={
            "events": "https://api.elections.kalshi.com/trade-api/v2/events?",
            "orders": "https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook?depth=0"
        },
        method="GET",
        active=True
    )
]