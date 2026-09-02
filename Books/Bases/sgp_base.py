import inspect
import re
import urllib.parse
from abc import abstractmethod
from functools import wraps
from Books.Bases.book_base import BookBase
from loguru import logger
from curl_cffi import AsyncSession as CurlAsyncSession
from Redis.redis_manager import RedisAsyncManager


class SGPBookBase(BookBase):
    def __init__(self, book_name: str, sgp_data: dict, **kwargs):
        if kwargs.get("optional_db") is not None:
            self.optional_redis_instance = RedisAsyncManager(database=kwargs.get("optional_db", 0))

        super().__init__(book_category="sgp", book_name=book_name, redis_database=None)
        self.sgp_data = sgp_data
        self._parse_sgp_data(sgp_data)
        self.extras = kwargs
        self.auth_redis_manager = RedisAsyncManager(database=1)

        if self.book_data.auth_job_dict:
            self.auth_id_name = self.book_data.auth_job_dict.auth_redis_key
        self.mapper_redis_manager = RedisAsyncManager(database=2)
        if self.book_data.mapper_job_dict:
            self.mapper_id_name = self.book_data.mapper_job_dict.mapper_redis_key


    @abstractmethod
    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        raise NotImplementedError("Subclasses must implement the run_book method.")

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

    def _parse_sgp_data(self, sgp_data: dict):
        self.links = sgp_data.get("links", [])
        self.link_data = self._extract_link_details()

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
    def return_odds(american_odds: str | float | int | None, decimal_odds: str | float | int | None) -> dict:
        valid_types = (str, int, float)

        odds = {}

        if isinstance(american_odds, valid_types):
            odds.update({"american_odds": round(float(american_odds), 2)})

        if isinstance(decimal_odds, valid_types):
            odds.update({"decimal_odds": round(float(decimal_odds),2)})

        if not isinstance(american_odds, valid_types) and not isinstance(decimal_odds, valid_types):
            _stack = inspect.stack()[1]
            logger.info(f"{_stack[0].f_locals['self'].__class__.__name__}.{_stack[3]} - Failed to convert odds to float | American: {american_odds} ({type(american_odds)}) | Decimal: {decimal_odds} ({type(decimal_odds)}")
            return {}

        return odds
