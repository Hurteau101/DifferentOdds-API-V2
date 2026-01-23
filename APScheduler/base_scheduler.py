from abc import ABC, abstractmethod
import aiohttp
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import APICaller, SportbookRequestType


class BaseScheduler(APICaller, ABC):
    def __init__(self, request_type: SportbookRequestType):
        super().__init__(request_type=request_type)

    @abstractmethod
    async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
        raise NotImplementedError("Subclasses must implement the run_scheduler method.")