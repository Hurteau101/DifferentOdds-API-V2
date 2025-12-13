import json
import re
from abc import ABC, abstractmethod
from orjson import orjson
import urllib.parse
from Redis.redis_manager import RedisManager
from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig
from Settings.Mixin.mixins import ApiResponseMixin

class SGPBookBase(ApiResponseMixin, BookBase, ABC):
    """Base class for SGP books, inheriting from SportsbookBase."""
    def __init__(self, request_type, sportsbook_name: str, links, log_directory="SGP Logs", log_name=None, decode_url=False, skip_link_validation=False):
        self.book_data = SportsbookConfig.get_sgp_provider(sportsbook_name)
        self.link_data = self._extract_link_details(links, decode_url=decode_url, skip_link_validation=skip_link_validation)
        self.redis_db = 2
        super().__init__(request_type, log_directory=log_directory, log_name=log_name)


    @abstractmethod
    async def run_book(self):
        """Run the SGP book logic."""
        pass

    async def _returned_mapped_redis_data(self, sportsbook_name):
        redis = RedisManager(db=self.redis_db)
        mapped_ids = await redis.fetch_data(sportsbook_name)
        await redis.close()

        if isinstance(mapped_ids, bytes):
            mapped_ids = orjson.loads(mapped_ids)
        if isinstance(mapped_ids, str):
            mapped_ids = json.loads(mapped_ids)

        if not mapped_ids:
            self.file_logger.log(
                sportsbook=sportsbook_name,
                message="No mapped IDs found in Redis",
                level="ERROR",
            )

            return None

        return mapped_ids


    @staticmethod
    def require_link_data(func):
        """Decorator to ensure there is link data before running the function."""
        async def wrapper(self):
            if not getattr(self, "link_data", None):
                return None
            return await func(self)
        return wrapper

    def _extract_link_details(self, links, decode_url, skip_link_validation):
        """ Extract bet_id and event_id from the provided links."""
        if skip_link_validation:
            return links

        link_data = []

        for link in links:
            if decode_url:
                link = urllib.parse.unquote(link)

            if not link:
                return None

            bet_id = re.search(self.book_data.regex.get("bet_id_regex"), link)
            event_id = re.search(self.book_data.regex.get("event_id_regex"), link)

            if bet_id and event_id:
                bet_id = bet_id.group(1)

                link_data.append({
                    "bet_id": bet_id,
                    "event_id": event_id.group(1)
                })

        return link_data if link_data else None


