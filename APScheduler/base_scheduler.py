from abc import ABC, abstractmethod
import aiohttp
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import APICaller
from curl_cffi import AsyncSession as CurlAsyncSession

class BaseScheduler(APICaller, ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        raise NotImplementedError("Subclasses must implement the run_scheduler method.")