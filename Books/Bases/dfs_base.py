from abc import ABC, abstractmethod
from Books.Bases.book_base import BookBase
from datetime import datetime, timezone

class DFSBookBase(BookBase, ABC):
    def __init__(self, book_name: str):
        super().__init__(book_category="dfs", book_name=book_name, redis_database=0)
        self.esport_leagues = ["LOL", "CS2", "DOTA2", "VAL", "COD", "APEX", "R6"]

    @abstractmethod
    async def run_book(self) -> list | None:
        raise NotImplementedError("Subclasses must implement the run_book method.")

    def yield_game_data(self, book_data):
        """Helper function to yield game data from nested lists. Must follow specific structure of list of lists.
        With no inner function call to extract data"""
        for game in book_data:
            for game_data in game:
                if game_data:
                    yield game_data

    async def store_data(self, data_to_store: dict | list, key_name: str, expiration_time: int = None):
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


        wrapped_data = {
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "data": data_to_store
        }

        await self.redis_manager.store_data(
            key_name=f"{key_name}:game",
            data_to_store=data_to_store,
            key_expiration=expiration_time
        )

        await self.redis_manager.store_data(
            key_name=f"{key_name}:base",
            data_to_store=wrapped_data,
            key_expiration=expiration_time
        )
