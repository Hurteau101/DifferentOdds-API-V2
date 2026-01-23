from Monitoring.monitoring import init_sentry
init_sentry()

import asyncio
from Database.database import Database
from Redis.redis_manager import RedisAsyncManager


async def store_api_keys(database_instance: Database, redis_instance: RedisAsyncManager):
    api_keys = database_instance.get_api_keys()

    await redis_instance.store_data(
        key_name="api_keys",
        data_to_store=api_keys,
        key_expiration=3600  # 1 Hour
    )

    await redis_instance.close_for_shutdown()

if __name__ == "__main__":
    db = Database()
    redis_instance = RedisAsyncManager(database=11)
    asyncio.run(store_api_keys(database_instance=db, redis_instance=redis_instance))



