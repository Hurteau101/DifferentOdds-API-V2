from APScheduler.base_scheduler import BaseScheduler
from Redis.redis_manager import RedisAsyncManager, static_mapping_service
from Settings.book_configurations import BookConfiguration


class BaseMapper(BaseScheduler):
    def __init__(self, category: str, book_name: str,
                 default_key_expiration: int = 800):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        super().__init__()
        self.default_key_expiration = default_key_expiration

    @staticmethod
    def get_static_mapping():
        return static_mapping_service.get()