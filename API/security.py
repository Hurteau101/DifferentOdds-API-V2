from cachetools import TTLCache
from fastapi import Depends, Security, HTTPException
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED
from Redis.redis_manager import RedisAsyncManager

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
_api_cache = TTLCache(maxsize=1, ttl=600)  # Cache for 10 minutes

async def get_api_keys():
    # Cache the API keys to reduce redis calls.
    if "api_keys" not in _api_cache:
        redis_instance = RedisAsyncManager(database=10)
        api_data = await redis_instance.get_data(key_name="api_keys")
        if not api_data:
            return set()

        api_keys = set(
            key.get("api_key")
            for key in api_data
        )

        _api_cache["api_keys"] = api_keys if api_keys else set()

    return _api_cache["api_keys"]


async def get_api_key(api_key: str = Security(api_key_header), valid_keys: set[str] = Depends(get_api_keys)):
    """Checks if an API key is valid."""
    if api_key in valid_keys:
        return api_key
    raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")