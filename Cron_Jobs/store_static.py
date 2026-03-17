"""Used to store static data into Redis Database"""
from Monitoring.monitoring import init_sentry
init_sentry()


import asyncio
from Database.database import Database
from Redis.redis_manager import RedisAsyncManager


async def store_static(database_instance: Database, table_name: str, redis_instance: RedisAsyncManager):
    stored_data = database_instance.fetch_all(table_name=table_name)

    if table_name == "league_mapper":
        mapped_data = {
            record[0]: {
                "raw_name": record[0],
                "mapped_name": record[1],
                "sport": record[3]
            }
            for record in stored_data
        }

    elif table_name == "stat_mapper":
        mapped_data = {
            record[0]: record[1]
            for record in stored_data
        }
    else:
        return

    await redis_instance.store_data(
        key_name=table_name,
        data_to_store=mapped_data,
        key_expiration=1200  # 20 Minutes
    )


if __name__ == "__main__":
    db = Database()
    redis_instance = RedisAsyncManager(database=11)
    tables = ["stat_mapper", "league_mapper"]
    async def main():
        for table in tables:
            await store_static(database_instance=db, table_name=table, redis_instance=redis_instance)

        await redis_instance.close_for_shutdown()

    asyncio.run(main())








