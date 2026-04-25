"""
Special Book Mapper
- These are books that have special cases where running in APScheduler will not work, as they need to be mapped fast
and there are no restrictions on API calls.
- Example Bovada, we need to run it every 1 minute, due to there outcome ids changing. A line for 3.5 outcome ID will be
123 one minute then they will change the 2.5 to be the same id of 123, which causes wrong SGP odds. Running this every minute
helps relieve this issue to an extent.
"""
import aiohttp
from External_Book_Mapping.SGP.bovada_mapper import BovadaMapper
from Redis.redis_manager import RedisAsyncManager
import asyncio


async def run_bovada_mapper():
    redis_instance = RedisAsyncManager(database=2)
    mapper = BovadaMapper()
    async with aiohttp.ClientSession() as session:
        await mapper.run_scheduler(session=session, redis_instance=redis_instance)


if __name__ == "__main__":
    asyncio.run(run_bovada_mapper())