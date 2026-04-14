
import os
import re
import urllib.parse
from abc import abstractmethod, ABC

from tenacity import AsyncRetrying, retry_if_result, wait_fixed, stop_after_attempt
from functools import wraps
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import APICaller, SportbookRequestType
from Redis.redis_manager import RedisAsyncManager


class SGPBookBase(APICaller, ABC):
    def __init__(self, request_type: SportbookRequestType, category: str,
                 book_name: str, sgp_data: dict, retry_amount: int = 3,
                 retry_wait_interval: int = 1, regex_keys: list = None, mapped_ids_redis_instance=None, auth_redis_instance=None,
                 **kwargs):
        self.regex_keys = regex_keys or ["bet_id", "event_id"]
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        self._parse_sgp_data(sgp_data)
        self.sgp_data = sgp_data
        self.extras = kwargs
        self.retry_amount = retry_amount
        self.retry_wait_interval = retry_wait_interval
        self.mapped_ids_redis_instance = mapped_ids_redis_instance
        self.auth_redis_instance = auth_redis_instance

        super().__init__(request_type=request_type)

    @abstractmethod
    async def run_book(self, session=None):
        raise NotImplementedError("Subclasses must implement the run_book method.")

    def _parse_sgp_data(self, sgp_data: dict):
        self.links = sgp_data.get("links", [])
        self.link_data = self._extract_link_details()


    @staticmethod
    def ensure_link_data(func):
        """Decorator to ensure there is link data before running the function."""
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            link_data = getattr(self, "link_data", [])
            if not link_data:
                return None
            return await func(self, *args, **kwargs)
        return wrapper

    @staticmethod
    def return_odds(american_odds: str | float | int | None, decimal_odds: str | float | int | None) -> dict:
        try:
            return {
                "american": float(american_odds) if american_odds else None,
                "decimal": float(decimal_odds) if decimal_odds else None
            }
        except:
            print(f"*************** THIS FAILED TO CONVERT ODDS ({american_odds} {decimal_odds}) ***************")
            return {}

    async def load_auth_token(self, key_name: str):
        """Returns the stored auth token from Redis."""
        return await self.auth_redis_instance.get_data(key_name)

    async def load_book_data(self, key_name: str):
        """Returns the stored book data from Redis."""

    async def load_mapped_ids(self, key_name: str):
        """Returns the stored mapped ids from Redis."""
        return await self.mapped_ids_redis_instance.get_data(key_name)


    # @staticmethod
    # def ensure_mapped_data(func):
    #     async def wrapper(self):
    #         mapped_data = getattr(self, "mapped_ids", {})
    #         if not mapped_data:
    #             return None
    #         return await func(self)
    #     return wrapper

    def _extract_link_details(self) -> list[dict]:
        """ Extract IDs from the provided links based on regex patterns."""
        return [
            {
                id_name: match.group(1)
                for id_name, reg_pattern in (self.book_data.regex or {}).items()
                if (match := re.search(reg_pattern, urllib.parse.unquote(link)))
            }
            for link in self.links
        ]

    @staticmethod
    def convert_decimal_to_american(decimal_odds):
        """Convert decimal odds to American odds."""
        if decimal_odds is None:
            return None
        if decimal_odds >= 2.0:
            return float(round((decimal_odds - 1) * 100))
        else:
            return float(round(-100 / (decimal_odds - 1)))

    @staticmethod
    def convert_probability_to_american_odds(probability_str: str | float):
        """Converts a probability to American odds."""
        probability = float(probability_str)

        if not 0 <= probability <= 1:
            return None

        if probability == 0:
            return None
        if probability == 1:
            return None

        if probability > 0.5:
            american_odds = -(100 * probability) / (1 - probability)
        else:
            american_odds = (100 * (1 - probability)) / probability

        return round(american_odds)

    @staticmethod
    def retry_book(is_disabled: bool = False):
        def decorator(func):

            if is_disabled:
                return func

            @wraps(func)
            async def wrapper(self, *args, **kwargs):

                async for attempt in AsyncRetrying(
                        retry=retry_if_result(lambda result: result is None),
                        wait=wait_fixed(self.retry_wait_interval),
                        stop=stop_after_attempt(self.retry_amount),
                        retry_error_callback=lambda retry_state: None,
                ):
                    with attempt:
                        result = await func(self, *args, **kwargs)

                return result

            return wrapper

        return decorator

