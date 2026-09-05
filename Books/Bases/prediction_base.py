from abc import abstractmethod
from Books.Bases.book_base import BookBase
from Redis.redis_manager import RedisAsyncManager


class PredictionBookBase(BookBase):
    LEAGUE_STAT_OVERRIDES = {
        "NHL": {
            "total points": "Total Goals",
            "spread": "Puck Line",
        },
        "MLB": {
            "total points": "Total Runs",
            "spread": "Run Line",
        },
    }

    def __init__(self, book_name: str):
        super().__init__(book_category="prediction_liquidity", book_name=book_name, redis_database=0)
        self.redis_auth_manager = RedisAsyncManager(database=1)

    @abstractmethod
    async def run_book(self) -> list | None:
        raise NotImplementedError("Subclasses must implement the run_book method.")

    def special_stat_mapper(self, stat_type: str, league: str) -> str:
        overrides = self.LEAGUE_STAT_OVERRIDES.get(league, {})
        return overrides.get(stat_type.lower(), stat_type)