from typing import Optional
from Settings.Providers.base_provider import BaseProvider
from dataclasses import dataclass



PREDICTION_LIQUIDITY_PROVIDERS = [
    BaseProvider(
        title="4cx",
        name="4cx",
        url={
            "games": "https://api.4cx.io/exchange/getLeagues",
            "orders": "https://api.4cx.io/exchange/getOrderbook"
        },
        headers={
            'Origin': 'https://4cx.io',
            'Connection': 'keep-alive',
            'Referer': 'https://4cx.io/',
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
        title="Novig",
        name="novig",
        url={
            "base_url": "https://gql.novig.us/v1/graphql",
            "league_url": "https://api.novig.us/recs/v1/tabs/rankings"
        },
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
        is_active=True
    ),
    BaseProvider(
        title="Prophetx",
        name="prophetx",
        url={
            "events_url": "https://cash.api.prophetx.co/partner/affiliate/get_sport_events",
            "markets_url": "https://cash.api.prophetx.co/partner/v3/affiliate/get_multiple_markets"
        },

        method="GET",
        is_active=True
    ),
]
