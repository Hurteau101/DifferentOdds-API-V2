import os
import ssl
import redis.asyncio as redis
import redis as redis_sync
from dotenv import load_dotenv
from orjson import orjson
from redis.exceptions import LockError, RedisError
import logging
from dataclasses import is_dataclass
from old.Settings.book_base import BookBase

#####################################
####### REDIS COMMANDS ##########
## redis-cli -n 2 KEYS "*" - # List all keys in database 2
## redis-cli -n 2 FLUSHDB - # Clear all keys in database 2
######################################

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class RedisManager:
    def __init__(self, db=0, port=6379, max_connections=50):
        self.redis_client = redis.Redis(
            host='localhost',
            port=port,
            db=db,
            decode_responses=False,
            max_connections=max_connections
        )

    def clone_with_db(self, db: int):
        return RedisManager(db=db)

    async def store_auth_token(self, key_name, value, key_expiration=None):
        try:
            if key_expiration:
                await self.redis_client.set(key_name, value, ex=key_expiration)
            else:
                await self.redis_client.set(key_name, value)

            logging.info(f"Stored plain text token for {key_name}")
        except Exception as e:
            logging.error(f"Error storing plain text for {key_name}: {e}")

    async def get_auth_token(self, key_name):
        try:
            cached_data = await self.redis_client.get(key_name)
            return cached_data.decode('utf-8')
        except Exception as e:
            logging.error(f"Error fetching plain text for {key_name}: {e}")
            return None

    async def fetch_data(self, key_name: str):
        """Fetch and deserialize JSON data from Redis."""
        try:
            cached_data = await self.redis_client.get(key_name)
            if not cached_data:
                return None
            return orjson.loads(cached_data)
        except (orjson.JSONDecodeError, RedisError) as e:
            logging.error(f"Error fetching {key_name}: {e}")
            return None

    async def store_data(self, key_name, data_to_store, timeout=60, blocking_timeout=10, key_expiration=None):
        """Store data in Redis as raw JSON bytes (fast, no compression)."""
        lock = self.redis_client.lock(
            f"{key_name}_lock",
            timeout=timeout,
            blocking_timeout=blocking_timeout
        )
        try:
            async with lock:
                if is_dataclass(data_to_store):
                    data_to_store = BookBase.serialize_data(data_to_store)

                data_bytes = orjson.dumps(data_to_store)
                # compressed = gzip.compress(data_bytes, compresslevel=1)

                if key_expiration:
                    success = await self.redis_client.set(key_name, data_bytes, ex=key_expiration)
                else:
                    success = await self.redis_client.set(key_name, data_bytes)

                if success:
                    logging.info(f"Stored data for {key_name} successfully.")
                else:
                    logging.error(f"Failed to store data for {key_name}.")
        except (LockError, RedisError) as e:
            logging.error(f"Redis error storing {key_name}: {e}")


    async def close(self):
        """Close the Redis connection."""
        await self.redis_client.close()

    async def delete(self, key_name: str):
        """Delete a key from Redis."""
        try:
            await self.redis_client.delete(key_name)
            return
        except (LockError, RedisError) as e:
            return

class RedisRemote:
    def __init__(self, redis_db=2):
        load_dotenv()
        ca_cert_path = os.path.join(BASE_DIR, "certs", "ca.crt")

        if not os.path.exists(ca_cert_path):
            raise FileNotFoundError(f"CA certificate not found at: {ca_cert_path}")

        self.redis_client = redis_sync.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            username=os.getenv("REDIS_USERNAME"),
            password=os.getenv("REDIS_PASSWORD"),
            ssl=True,
            db=redis_db,
            ssl_ca_certs=ca_cert_path,
            ssl_cert_reqs=ssl.CERT_REQUIRED,
            ssl_check_hostname=False,
        )

    def get_all_key_values(self, count=5000):
        """
        Retrieves all values from the Redis database.
        """
        cursor = 0
        all_keys = []
        result = []

        # Collect keys
        while True:
            cursor, batch = self.redis_client.scan(cursor=cursor, count=count)
            all_keys.extend(batch)
            if cursor == 0:
                break

        pipe = self.redis_client.pipeline()
        for key in all_keys:
            pipe.get(key)
        values = pipe.execute()

        for value in values:
            if value is None:
                continue

            try:
                result.append(orjson.loads(value))
            except:
                result.append(value.decode())

        return result

class RedisSync:
    def __init__(self, db=3, host="localhost", port=6379):
        self.client = redis_sync.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=False
        )

    def get(self, key):
        return self.client.get(key)

    def set(self, key, value, ex=None):
        return self.client.set(key, value, ex=ex)