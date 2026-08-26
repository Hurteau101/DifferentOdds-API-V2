from APScheduler.base_scheduler import BaseScheduler
from Redis.redis_manager import RedisAsyncManager, static_mapping_service
from Settings.book_configurations import BookConfiguration


class BaseMapper(BaseScheduler):
    def __init__(self, category: str, book_name: str,
                 default_key_expiration: int = 800):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        super().__init__()
        self.default_key_expiration = default_key_expiration
        self.mapper_id_name = self.book_data.mapper_job_dict.mapper_redis_key
        if not self.mapper_id_name:
            raise KeyError(f"Ensure {self.book_data.name} has a 'mapper_redis_key'")

    @staticmethod
    def get_static_mapping():
        return static_mapping_service.get()