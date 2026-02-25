from Settings.Providers.DFS.dfs_providers import DFS_PROVIDERS
from Settings.Providers.SGP.sgp_providers import SGP_PROVIDERS
from Settings.Providers.Sportsbooks.sportsbooks_providers import SPORTSBOOKS_PROVIDERS
from Settings.Providers.Prediction_Liquidity.prediction_liquidity_providers import PREDICTION_LIQUIDITY_PROVIDERS

NAMES_MAPPER = {
    "DFS": DFS_PROVIDERS,
    "SGP": SGP_PROVIDERS,
    "SPORTSBOOKS": SPORTSBOOKS_PROVIDERS,
    "PREDICTION_LIQUIDITY": PREDICTION_LIQUIDITY_PROVIDERS
}

class BookConfiguration:
    @classmethod
    def get_provider(cls, category: str, book_name: str):
        if not category or not book_name:
            raise ValueError("Both 'category' and 'book_name' must be provided.")

        category = category.upper()

        if category not in NAMES_MAPPER:
            raise ValueError(f"Category '{category}' is not recognized.")

        providers = NAMES_MAPPER.get(category)
        if providers is None:
            raise ValueError(f"Category '{category}' not found.")

        return next(provider for provider in providers if provider.name.lower() == book_name.lower())

    @staticmethod
    def get_book_info(book_type):
        return  [
            {
                "title": name.title,
                "book_key": name.name,
                "status": True if name.is_active else False
            }
            for name in NAMES_MAPPER.get(book_type.upper(), [])
        ]