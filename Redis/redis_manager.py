import json

import redis.asyncio as redis
from redis.exceptions import LockError, RedisError
import logging
from dataclasses import is_dataclass
from Settings.book_base import BookBase

#####################################
####### REDIS COMMANDS ##########
## redis-cli -n 2 KEYS "*" - # List all keys in database 2
## redis-cli -n 2 FLUSHDB - # Clear all keys in database 2
######################################


class RedisManager:
    def __init__(self, db=0, port=6379, max_connections=50):
        self.redis_client = redis.Redis(
            host='localhost',
            port=port,
            db=db,
            decode_responses=True,
            max_connections=max_connections
        )

    async def fetch_data(self, key_name):
        """Fetch data from Redis with a lock to prevent concurrent access issues."""
        lock = self.redis_client.lock(f"{key_name}_lock", timeout=30, blocking_timeout=10)
        try:
            async with lock:
                print(f"Fetching data for {key_name}")
                logging.info(f"Fetching data for {key_name}")
                return await self.redis_client.get(key_name)
        except LockError:
            logging.error(f"Skipping {key_name}. Another process might be using it.")
            return None

    async def store_data(self, key_name, data_to_store, timeout=60, blocking_timeout=10, key_expiration=60):
        """Store data in Redis with a lock to prevent concurrent access issues."""
        lock = self.redis_client.lock(f"{key_name}_lock", timeout=timeout, blocking_timeout=blocking_timeout)
        try:
            async with lock:
                if is_dataclass(data_to_store):
                    data_to_store = BookBase.serialize_data(data_to_store)
                elif isinstance(data_to_store, dict):
                    data_to_store = json.dumps(data_to_store)

                success = await self.redis_client.set(key_name, data_to_store, ex=key_expiration)

                if success:
                    logging.info(f"Stored data for {key_name} successfully.")
                else:
                    logging.error(f"Failed to store data for {key_name}.")

        except LockError:
            logging.error(f"Skipping {key_name}. Another process might be using it.")

        except RedisError as e:
            logging.error(f"Redis error for {key_name}: {e}")

    async def close(self):
        """Close the Redis connection."""
        await self.redis_client.close()
