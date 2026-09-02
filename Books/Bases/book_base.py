from dotenv import load_dotenv
load_dotenv()

import asyncio
from Redis.redis_manager import static_mapping_service
from abc import ABC
from Redis.redis_manager import RedisAsyncManager
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import APICaller
from loguru import logger
import re


class BookBase(ABC):
    def __init__(self, book_category: str, book_name: str, redis_database: int | None, redis_expiration: int = 600):
        self.book_data = BookConfiguration.get_provider(category=book_category, book_name=book_name)

        if redis_database is not None:
            self.redis_manager = RedisAsyncManager(database=redis_database)

        self.redis_expiration = redis_expiration
        self.impersonate = self._get_impersonate(book_name=book_name, category=book_category)
        self.api_instance = APICaller()
        self.api_caller = self.api_instance.api_caller
        self.static_mapping = static_mapping_service.get()

    def _get_impersonate(self, category: str, book_name: str):
        """Get the impersonate set in the book provider"""
        config = BookConfiguration.get_provider(category=category, book_name=book_name)
        return config.curl_impersonation

    @staticmethod
    def generate_key(key_data) -> str | None:
        """Generate a unique key based on the provided data."""
        if not key_data or not isinstance(key_data, list) or None in key_data:
            return None

        generate_key = sorted(key_data, reverse=True)
        return "_".join([str(key.replace(" ", "_")).lower() for key in generate_key])

    def split_colon_at_proxy(self, proxy: str) -> list | None:
        """Splits a proxy string into parts based on the colon (:) & (@) characters."""
        parts = re.split(r'[:@]', proxy, maxsplit=3)

        if len(parts) != 4:
            logger.error(f"Invalid proxy format: {proxy}")
            return None

        return parts

    def _special_mapping(self, mapping_name: str, league: str):
        """Used to map special market names to the correct names based on the league."""
        if not mapping_name or not league:
            return None

        mapping_name_lower = mapping_name.lower()

        if mapping_name_lower == "point spread":
            mapping_name_lower = "spread"

        league = league.upper()

        special_mapping = {
            "NHL": {
                "spread": "Puck Line",
                "total": "Total Goals",
            },
            "MLB": {
                "spread": "Run Line",
                "total": "Total Runs",
            }
        }

        found_mapping = special_mapping.get(league, {}).get(mapping_name_lower)

        return found_mapping if found_mapping else mapping_name


    async def store_data(self, data_to_store: dict | list | str, key_name: str, expiration_time: int = None):
        """
        Store data in Redis with a specified key and expiration time.
        :param data_to_store: The data to be stored.
        :param key_name: The name of the book.
        :param expiration_time: The expiration time for the data in seconds. If not provided, the default expiration time is used.
        """
        if not data_to_store:
            return

        if not expiration_time:
            expiration_time = self.redis_expiration

        await self.redis_manager.store_data(
            data_to_store=data_to_store,
            key_name=key_name,
            key_expiration=expiration_time
        )

    def add_to_events(self, events: dict, item, game_data_cls):
        """Helper to add sportsbook data to events dictionary grouped by team_key."""
        key = item.game_key

        if key not in events:
            events[key] = game_data_cls(
                game_key=key,
                league=item.league,
                start_date=item.start_date,
                team_data=item.team_data,
                solo_game=item.solo_game,
                odds=[],
            )

        events[key].odds.extend(item.odds)

    async def post_with_semaphore(self, semaphore: asyncio.Semaphore, task, retries: int = 3, delay: float = 1.0):
        async with semaphore:
            for attempt in range(retries):
                try:
                    await asyncio.sleep(0.5)
                    return await task
                except Exception as e:
                    if attempt == retries - 1:
                        return None
                    await asyncio.sleep(delay * (attempt + 1))

            return None