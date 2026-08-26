from APScheduler.base_scheduler import BaseScheduler
from Redis.redis_manager import RedisAsyncManager, static_mapping_service
from Settings.book_configurations import BookConfiguration


class BaseAuth(BaseScheduler):
    def __init__(self, category: str, book_name: str, default_key_expiration: int = 800):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        super().__init__()
        self.default_key_expiration = default_key_expiration
        self.auth_id_name = self.book_data.auth_job_dict.auth_redis_key
        if not self.auth_id_name:
            raise KeyError(f"Ensure {self.book_data.name} has a 'mapper_redis_key'")