from Monitoring.monitoring import init_sentry
init_sentry()

import asyncio
from Database.database import Database
from Redis.redis_manager import RedisAsyncManager
from decimal import Decimal

async def store_auto_sgp_configs(database_instance: Database, redis_instance: RedisAsyncManager):
    configs = database_instance.get_auto_sgp_configs()

    modified_configs = [
        {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in row.items()
        }
        for row in configs
    ]

    await redis_instance.store_data(
        key_name="configs",
        data_to_store=modified_configs,
        key_expiration=3600  # 1 Hour
    )

    await redis_instance.close_for_shutdown()

if __name__ == "__main__":
    db = Database()
    redis_instance = RedisAsyncManager(database=8)
    asyncio.run(store_auto_sgp_configs(database_instance=db, redis_instance=redis_instance))