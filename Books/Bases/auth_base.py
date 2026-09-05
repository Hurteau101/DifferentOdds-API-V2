from abc import abstractmethod
from Books.Bases.book_base import BookBase

class AuthBase(BookBase):
    def __init__(self, category: str, book_name: str, redis_expiration: int = 800, precalculated_additional_time: int = 180):
        super().__init__(book_category=category, book_name=book_name, redis_database=1, redis_expiration=redis_expiration)
        self.auth_id_name = self.book_data.auth_job_dict.auth_redis_key
        # Used based on the APScheduler interval time, to ensure there isn't a time when there is no key in Redis.
        self.pre_calculated_redis_expiration = self.book_data.auth_job_dict.ap_scheduler.interval + precalculated_additional_time

        if not self.auth_id_name:
            raise KeyError(f"Ensure {self.book_data.name} has a 'mapper_redis_key'")

    @abstractmethod
    async def run_auth(self) -> bool:
        raise NotImplementedError("Subclasses must implement the run_auth method.")
