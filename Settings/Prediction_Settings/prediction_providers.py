from dataclasses import dataclass
from typing import Optional


@dataclass
class PredictionProvider:
    title: str
    name: str
    url: dict
    method: str
    active: bool
    headers: Optional[dict] = None


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
    ),
    PredictionProvider(
        title="4cx",
        name="4cx",
        url={
            "games": "https://api.4cx.io/exchange/getOrderbookPaginated?leagueRequested={league}&sportRequested={sport}",
            "orders": "https://api.4cx.io/exchange/getSingleOrderbook"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Origin': 'https://4cx.io',
            'Connection': 'keep-alive',
            'Referer': 'https://4cx.io/',
        },
        method="GET",
        active=True
    )
]