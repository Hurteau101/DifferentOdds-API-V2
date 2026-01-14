from Settings.Sportsbook_Settings.sportsbook_providers import SPORTSBOOK_PROVIDERS, SportsbookProvider
from Settings.dfs_providers import DFS_PROVIDERS, DFSProvider
from Settings.sgp_providers import SGPProvider, SGP_PROVIDERS
from Settings.Prediction_Settings.prediction_providers import PREDICTION_PROVIDERS, PredictionProvider
from Settings.sgp_mapper_providers import SGPMapperProviders, SGP_MAPPER_PROVIDERS
from Settings.pph_providers import PPH_PROVIDERS, PPHProvider
from Settings.Liquidity_Settings.liquidity_providers import LIQUIDITY_PROVIDERS, LiquidityProvider

NAMES_MAPPER = {
    "dfs": DFS_PROVIDERS,
    "sgp": SGP_PROVIDERS,
    "prediction": PREDICTION_PROVIDERS,
    "sgp_mapper": SGP_MAPPER_PROVIDERS,
    "pph": PPH_PROVIDERS,
    "liquidity": LIQUIDITY_PROVIDERS,
    "sportsbooks": SPORTSBOOK_PROVIDERS
}

# This module provides configuration for DFS, Sportsbooks, Exchanges & SGP Mapper Provders.
class SportsbookConfig:
    @classmethod
    def get_dfs_provider(cls, name: str) -> DFSProvider:
        try:
            return next(provider for provider in DFS_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"DFS provider '{name}' not found.")

    @classmethod
    def get_prediction_provider(cls, name: str) -> PredictionProvider:
        try:
            return next(provider for provider in PREDICTION_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Prediction provider '{name}' not found.")

    @classmethod
    def get_sgp_provider(cls, name:str) -> SGPProvider:
        try:
            return next(provider for provider in SGP_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Sportsbook provider '{name}' not found.")

    @classmethod
    def get_sgp_mapper_provider(cls, name:str) -> SGPMapperProviders:
        try:
            return next(provider for provider in SGP_MAPPER_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"SGP Mapper provider '{name}' not found.")

    @classmethod
    def get_sportsbook_provider(cls, name: str) -> SportsbookProvider:
        try:
            return next(provider for provider in SPORTSBOOK_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Sportsbook provider '{name}' not found.")

    @classmethod
    def get_pph_provider(cls, name: str) -> PPHProvider:
        try:
            return next(provider for provider in PPH_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"PPH provider '{name}' not found.")

    @classmethod
    def get_liquidity_provider(cls, name: str) -> LiquidityProvider:
        try:
            return next(provider for provider in LIQUIDITY_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"Liquidity provider '{name}' not found.")

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


