import os
import ssl
import time
import redis
import redis.asyncio as async_redis
import orjson
from dotenv import load_dotenv


class RedisBaseManager:
    def __init__(self, **pool_kwargs):
        pool = async_redis.ConnectionPool(
            host=pool_kwargs.get("host", "localhost"),
            port=pool_kwargs.get("port", 6379),
            db=pool_kwargs.get("database", 0),
            decode_responses=pool_kwargs.get("decode_response", False),
            max_connections=pool_kwargs.get("max_connections", 50),
            **{k: v for k, v in pool_kwargs.items() if k not in {"host","port","database","decode_response","max_connections"}}
        )
        self.redis_client = async_redis.Redis(connection_pool=pool)

    async def store_data(self, key_name: str, data_to_store: any, key_expiration: int = None):
        """Store data in Redis after serializing."""
        if not key_name or not data_to_store:
            raise ValueError("Key name and/or data_to_store must be provided")

        if isinstance(data_to_store, str):
            data_bytes = data_to_store.encode('utf-8')
        else:
            data_bytes = orjson.dumps(data_to_store)

        await self.redis_client.set(
            name=key_name,
            value=data_bytes,
            ex=key_expiration
        )

    # Use only when the connection needs to be closed (like cron jobs). Do not use on celery tasks.
    async def close_for_shutdown(self):
        """Closes the Redis client and disconnects all connections in the pool."""
        await self.redis_client.aclose()
        await self.redis_client.connection_pool.disconnect(inuse_connections=True)

    @staticmethod
    def clean_data(data: any) -> any:
        """Cleans the data fetched from Redis by decoding bytes and attempting JSON deserialization."""
        if isinstance(data, bytes):
            try:
                return orjson.loads(data)
            except orjson.JSONDecodeError:
                return data.decode("utf-8")

        return data

    async def get_data(self, key_name: str) -> any:
        """Fetches and cleans the authentication token stored in Redis."""
        found_data = await self.redis_client.get(key_name)
        return RedisBaseManager.clean_data(found_data)

    async def get_all_key_values(self, count: int = 5000) -> list:
        """Retrieves all values from the Redis database."""
        cursor = 0
        all_keys = []
        result = []

        # Collect keys
        while True:
            cursor, batch = await self.redis_client.scan(cursor=cursor, count=count)
            all_keys.extend(batch)
            if cursor == 0:
                break

        pipe = await self.redis_client.pipeline()

        for key in all_keys:
            pipe.get(key)

        values = await pipe.execute()

        for value in values:
            cleaned_value = RedisBaseManager.clean_data(value)
            if not cleaned_value:
                continue

            result.append(cleaned_value)

        return result


class RedisAsyncManager(RedisBaseManager):
    def __init__(self, host: str = "localhost", database: int = 0, port: int = 6379, max_connections: int = 50,
                 decode_response: bool = False):
        super().__init__(
            host=host,
            port=port,
            database=database,
            max_connections=max_connections,
            decode_response=decode_response
        )


class RedisRemoteManager(RedisBaseManager):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    def __init__(self):
        load_dotenv()
        ca_cert_path = os.path.join(RedisRemoteManager.BASE_DIR, "certs", "ca.crt")
        if not os.path.exists(ca_cert_path):
            raise FileNotFoundError(f"CA certificate not found at {ca_cert_path}")

        super().__init__(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            database=int(os.getenv("REDIS_DB")),
            max_connections=100,
            decode_response=False,
            ssl=True,
            ssl_ca_certs = ca_cert_path,
            ssl_cert_reqs = ssl.CERT_REQUIRED,
            ssl_check_hostname = False,
        )


class RedisSyncManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        database: int = 0,
        decode_response: bool = False,
        **connection_kwargs,
    ):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=database,
            decode_responses=decode_response,
            **connection_kwargs,
        )

    def get_data(self, key_name: str):
        found_data = self.redis_client.get(key_name)
        return RedisBaseManager.clean_data(found_data)

    def store_data(self, key_name: str, data_to_store: any, key_expiration: int = None):
        if not key_name or data_to_store is None:
            raise ValueError("Key name and data_to_store must be provided")

        if isinstance(data_to_store, str):
            data_bytes = data_to_store.encode("utf-8")
        else:
            data_bytes = orjson.dumps(data_to_store)

        self.redis_client.set(
            name=key_name,
            value=data_bytes,
            ex=key_expiration,
        )

class RedisStaticMappingService:
    """Service to fetch and cache static mappings from Redis."""
    _cache = None
    _last_loaded = 0
    _ttl = 1200  # 20 minutes

    def __init__(self):
        self.redis = RedisSyncManager(database=11)

    def get(self):
        now = time.time()

        if self._cache is None or now - self._last_loaded > self._ttl:
            self._cache = {
                "stats": self.redis.get_data("stat_mapper") or {},
                "leagues": self.redis.get_data("league_mapper") or {}
            }

            self._last_loaded = now

        return self._cache

# Create a singleton instance for global use
static_mapping_service = RedisStaticMappingService()










