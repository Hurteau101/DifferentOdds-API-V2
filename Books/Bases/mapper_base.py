from abc import abstractmethod
from Books.Bases.book_base import BookBase
from Redis.redis_manager import RedisAsyncManager


class MapperBase(BookBase):
    def __init__(self, category: str, book_name: str, redis_expiration: int = 800, precalculated_additional_time: int = 180):
        super().__init__(book_category=category, book_name=book_name, redis_database=2, redis_expiration=redis_expiration)
        self.mapper_id_name = self.book_data.mapper_job_dict.mapper_redis_key
        self.pre_calculated_redis_expiration = self.book_data.mapper_job_dict.ap_scheduler.interval + precalculated_additional_time
        self.redis_auth_manager = RedisAsyncManager(database=1)
        if not self.mapper_id_name:
            raise KeyError(f"Ensure {self.book_data.name} has a 'mapper_redis_key'")

    @abstractmethod
    async def run_mapper(self) -> bool:
        raise NotImplementedError("Subclasses must implement the run_mapper method.")

    @staticmethod
    def build_prop_key(stat, side, line, player=None):
        """Builds a prop key based on the provided options."""
        valid_options = [
            option.strip().lower()
            for option in [stat, side, line, player]
            if option
        ]

        sorted_options = sorted(valid_options)
        return "_".join(sorted_options).lower().replace(" ", "_")