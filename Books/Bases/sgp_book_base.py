import re
import urllib.parse
from abc import abstractmethod, ABC
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import APICaller, SportbookRequestType
from Redis.redis_manager import RedisAsyncManager


class SGPBookBase(APICaller, ABC):
    def __init__(self, request_type: SportbookRequestType, category: str, book_name: str, sgp_data: dict,
                 regex_keys: list = None, mapped_ids: dict = None):
        self.regex_keys = regex_keys or ["bet_id", "event_id"]
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        self.mapped_ids = mapped_ids
        self._parse_sgp_data(sgp_data)
        super().__init__(request_type=request_type)

    @abstractmethod
    async def run_book(self):
        raise NotImplementedError("Subclasses must implement the run_book method.")

    def _parse_sgp_data(self, sgp_data: dict):
        self.links = sgp_data.get("links", [])
        self.link_data = self._extract_link_details()

    @staticmethod
    def ensure_link_data(func):
        """Decorator to ensure there is link data before running the function."""
        async def wrapper(self):
            link_data = getattr(self, "link_data", [])
            if not link_data:
                return None
            return await func(self)
        return wrapper

    @staticmethod
    def return_odds(american_odds: str | float | int | None, decimal_odds: str | float | int | None) -> dict:
        return {
            "american_odds": float(american_odds) if american_odds else None,
            "decimal_odds": float(decimal_odds) if decimal_odds else None
        }

    @staticmethod
    def ensure_mapped_data(func):
        async def wrapper(self):
            mapped_data = getattr(self, "mapped_ids", {})
            print(mapped_data)
            if not mapped_data:
                return None
            return await func(self)
        return wrapper

    def _extract_link_details(self) -> list[dict]:
        """ Extract IDs from the provided links based on regex patterns."""
        return [
            {
                id_name: urllib.parse.unquote(extracted_id.group(1))
                for id_name, reg_pattern in self.book_data.regex.items() or {}
                if (extracted_id := re.search(reg_pattern, link))
            }

            for link in self.links
        ]
