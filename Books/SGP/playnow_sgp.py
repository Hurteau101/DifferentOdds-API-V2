import asyncio
from Books.Bases.sgp_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class PlaynowSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="playnow", sgp_data=sgp_data, **kwargs)

    async def run_book(self, session: CurlAsyncSession | None = None) -> dict | None:
        pass


if __name__ == "__main__":
    pass