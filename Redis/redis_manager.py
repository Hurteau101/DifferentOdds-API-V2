import time
from datetime import datetime, timezone
from typing import Any

import orjson
import redis
import redis.asyncio as async_redis


class RedisBaseManager:
    def __init__(self, host: str = "localhost", database: int = 0, port: int = 6379,
                 max_connections: int = 50, decode_response: bool = False,
                 is_async: bool = True, **kwargs):
        redis_type = async_redis if is_async else redis
        self.redis_client = redis_type.Redis(
            host=host, port=port, db=database,
            max_connections=max_connections,
            decode_responses=decode_response,
            **kwargs,
        )

    @staticmethod
    def deserialize(raw: bytes | str | None) -> Any:
        if raw is None:
            return None
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError:
            return raw.decode("utf-8") if isinstance(raw, bytes) else raw

    @staticmethod
    def serialize(data_to_store: dict | list | set | str | bytes | int | float | bool) -> bytes:
        if isinstance(data_to_store, set):
            data_to_store = list(data_to_store)
        if isinstance(data_to_store, bytes):
            return data_to_store
        if isinstance(data_to_store, str):
            return data_to_store.encode("utf-8")

        return orjson.dumps(data_to_store)

    @staticmethod
    def bulk_insert_data(data_to_store: dict, pipeline) -> None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        for key, value in data_to_store.items():
            ttl = (
                    value.get("ttl") or value.get("game_date") or value.get("date")
                    or value.get("event_date") or value.get("start_date")
            )

            if not ttl:
                raise ValueError("ttl must be provided for each key")

            if isinstance(ttl, str):
                ttl = datetime.fromisoformat(ttl.replace("Z", "+00:00"))
            if isinstance(ttl, datetime):
                if ttl.tzinfo is None:
                    ttl = ttl.replace(tzinfo=timezone.utc)
                ttl = int(ttl.timestamp() * 1000)

            pipeline.set(key, orjson.dumps(value), pxat=max(int(ttl), now_ms + 60_000))


class RedisAsyncManager(RedisBaseManager):
    redis_client: async_redis.Redis

    def __init__(self, **kwargs):
        super().__init__(is_async=True, **kwargs)

    async def store_data(self, key_name: str, data_to_store: dict | list | set | str | bytes | int | float | bool, key_expiration: int | None = None):
        stored_data = self.serialize(data_to_store)
        await self.redis_client.set(key_name, stored_data, ex=key_expiration)

    async def get_data(self, key_name: str) -> Any:
        if not key_name:
            raise ValueError("Key name must be provided")

        found_data = await self.redis_client.get(key_name)
        return self.deserialize(found_data)

    async def get_all_key_values(self, count: int = 5000) -> list:
        cursor = 0
        all_keys = []
        result = []

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
            cleaned_value = self.deserialize(value)

            if cleaned_value is None:
                continue

            result.append(cleaned_value)

        return result

    async def flush_db(self):
        await self.redis_client.flushdb()

    async def bulk_insert_individual(self, data_to_store: dict):
        pipeline = await self.redis_client.pipeline()
        self.bulk_insert_data(data_to_store=data_to_store, pipeline=pipeline)
        return await pipeline.execute()

    async def close_for_shutdown(self):
        """Closes the Redis client and disconnects all connections in the pool."""
        await self.redis_client.aclose()
        await self.redis_client.connection_pool.disconnect(inuse_connections=True)

    async def delete_keys(self, keys: list | set):
        pipeline = await self.redis_client.pipeline()
        for key in keys:
            pipeline.unlink(key)
        await pipeline.execute()

    async def update_value(self, key: str, new_data: dict):
        new_data = self.serialize(new_data)
        await self.redis_client.set(key, new_data, keepttl=True)


class RedisSyncManager(RedisBaseManager):
    redis_client: redis.Redis

    def __init__(self, **kwargs):
        super().__init__(is_async=False, **kwargs)

    def store_data(self, key_name: str, data_to_store: dict | list | set | str | bytes | int | float | bool, key_expiration: int | None = None):
        stored_data = self.serialize(data_to_store)
        self.redis_client.set(key_name, stored_data, ex=key_expiration)

    def get_data(self, key_name: str) -> Any:
        if not key_name:
            raise ValueError("Key name must be provided")

        found_data = self.redis_client.get(key_name)
        return self.deserialize(found_data)

    def get_all_key_values(self, count: int = 5000) -> list:
        cursor = 0
        all_keys = []
        result = []

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
            cleaned_value = self.deserialize(value)

            if cleaned_value is None:
                continue

            result.append(cleaned_value)

        return result

    def flush_db(self):
        self.redis_client.flushdb()

    def bulk_insert_individual(self, data_to_store: dict):
        pipeline = self.redis_client.pipeline()
        self.bulk_insert_data(data_to_store=data_to_store, pipeline=pipeline)
        return pipeline.execute()

    def close_for_shutdown(self):
        self.redis_client.close()
        self.redis_client.connection_pool.disconnect(inuse_connections=True)

    def delete_keys(self, keys: list | set):
        pipeline = self.redis_client.pipeline()
        for key in keys:
            pipeline.unlink(key)
        pipeline.execute()

    def update_value(self, key: str, new_data: dict):
        new_data = self.serialize(new_data)
        self.redis_client.set(key, new_data, keepttl=True)

class RedisStaticMappingService:
    """Service to fetch and cache static mappings from Redis."""
    _cache = None
    _last_loaded = 0
    _ttl = 1200  # 20 minutes

    def __init__(self):
        self.redis = RedisSyncManager(database=9)

    def get(self):
        now = time.time()

        if self._cache is None or now - self._last_loaded > self._ttl:
            self._cache = {
                "static_mapping": self.redis.get_data("stat_mapper") or {},
                "league_mapping": self.redis.get_data("league_mapper") or {},
                "team_mapping": self.redis.get_data("team_mapper") or {},
            }

            self._last_loaded = now

        return self._cache

# Create a singleton instance for global use
static_mapping_service = RedisStaticMappingService()
