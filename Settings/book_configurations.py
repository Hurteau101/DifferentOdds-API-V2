from Settings.Providers.DFS.dfs_providers import DFS_PROVIDERS
from Settings.Providers.SGP.sgp_providers import SGP_PROVIDERS
from Settings.Providers.Sportsbooks.sportsbooks_providers import SPORTSBOOKS_PROVIDERS
from Settings.Providers.Prediction_Liquidity.prediction_liquidity_providers import PREDICTION_LIQUIDITY_PROVIDERS
from dataclasses import fields

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

        provider = next((provider for provider in providers if provider.name.lower() == book_name.lower()), None)
        if not provider:
            raise ValueError(f"Book '{book_name}' not found in category '{category}'. Please ensure you have this set in your provider file.")

        return provider

    @staticmethod
    def get_book_info(book_type, key_names: dict | None = None, remove_non_active: bool = True):
        """
        Get book info for a specific book type.
        :param book_type: The type of book to retrieve info for (ex. SGP, DFS, etc.).
        :param key_names: A dictionary, where the key is the field name in the BookInfo class and the value is the desired key name in the output dictionary.
        :param remove_non_active: If True, only active books will be included in the output.
        """
        if not key_names:
            key_names = {"title": "title", "name": "book_key", "is_active": "status"}

        return [
            {
                key_names.get(field.name, field.name): getattr(category, field.name)
                for field in fields(category)
                if field.name in key_names and (not remove_non_active or category.is_active)
            }
            for category in NAMES_MAPPER.get(book_type.upper(), [])
        ]