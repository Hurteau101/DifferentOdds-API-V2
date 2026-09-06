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

