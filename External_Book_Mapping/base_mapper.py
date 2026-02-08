from APScheduler.base_scheduler import BaseScheduler
from Redis.redis_manager import RedisAsyncManager
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import SportbookRequestType


class BaseMapper(BaseScheduler):
    def __init__(self, request_type: SportbookRequestType, category: str, book_name: str,
                 default_key_expiration: int = 800):
        self.book_data = BookConfiguration.get_provider(category=category, book_name=book_name)
        super().__init__(request_type=request_type)
        self.default_key_expiration = default_key_expiration