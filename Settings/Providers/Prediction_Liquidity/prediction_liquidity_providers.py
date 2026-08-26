from typing import Optional
from Settings.Providers.base_provider import BaseProvider, AuthJobDict, RedisSelector
from dataclasses import dataclass


@dataclass
class LiquidityProvider(BaseProvider):
    base_file_path = "Books.Prediction_Liquidity"



PREDICTION_LIQUIDITY_PROVIDERS = [
    LiquidityProvider(
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
        is_active=True,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            refresh_interval=86400, # 24 Hours
            job_active=True,
            auth_redis_key="4cx_auth_token"
        ),
        class_name="FourCX",
        file_name="fourcx",
    ),
    LiquidityProvider(
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
        is_active=True,
        class_name="Novig",
        file_name="novig",
    ),
    LiquidityProvider(
        title="Prophetx",
        name="prophetx",
        url={
            "events_url": "https://cash.api.prophetx.co/partner/affiliate/get_sport_events",
            "markets_url": "https://cash.api.prophetx.co/partner/v3/affiliate/get_multiple_markets"
        },

        method="GET",
        is_active=True,
        class_name="Prophetx",
        file_name="prophetx",
    ),
]
