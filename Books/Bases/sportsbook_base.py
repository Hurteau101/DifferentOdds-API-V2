from abc import abstractmethod
from Books.Bases.book_base import BookBase
from Redis.redis_manager import RedisAsyncManager


class SportsbooksBookBase(BookBase):
    def __init__(self, book_name: str):
        super().__init__(book_category="sportsbooks", book_name=book_name, redis_database=0)
        self.auth_redis_manager = RedisAsyncManager(database=1)
        if self.book_data.auth_job_dict:
            self.auth_id_name = self.book_data.auth_job_dict.auth_redis_key
        self.mapper_redis_manager = RedisAsyncManager(database=2)
        if self.book_data.mapper_job_dict:
            self.mapper_id_name = self.book_data.mapper_job_dict.mapper_redis_key

        self.espn_redis = RedisAsyncManager(database=8)

    @abstractmethod
    async def run_book(self) -> list | None:
        raise NotImplementedError("Subclasses must implement the run_book method.")