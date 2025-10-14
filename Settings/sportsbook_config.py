from Settings.dfs_providers import DFS_PROVIDERS, DFSProvider
from Settings.sgp_providers import SGPProvider, SGP_PROVIDERS
from Settings.prediction_providers import EXCHANGE_PROVIDERS, ExchangeProvider


NAMES_MAPPER = {
    "dfs": DFS_PROVIDERS,
    "sgp": SGP_PROVIDERS,
    "exchange": EXCHANGE_PROVIDERS
}

# This module provides configuration for DFS, Sportsbooks & Exchanges.
class SportsbookConfig:
    @classmethod
    def get_dfs_provider(cls, name: str) -> DFSProvider:
        try:
            return next(provider for provider in DFS_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"DFS provider '{name}' not found.")

    @classmethod
    def get_exchange_provider(cls, name: str) -> ExchangeProvider:
        try:
            return next(provider for provider in EXCHANGE_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Exchange provider '{name}' not found.")

    @classmethod
    def get_sgp_provider(cls, name:str) -> SGPProvider:
        try:
            return next(provider for provider in SGP_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Sportsbook provider '{name}' not found.")

    @staticmethod
    def get_book_info(book_type):
        return  [
            {
                "title": name.title,
                "book_key": name.name,
                "status": "Online" if name.active else "Offline"
            }
            for name in NAMES_MAPPER.get(book_type, [])
        ]


