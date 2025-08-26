from fastapi import Depends, Request, Security, HTTPException
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from Mapper.database import Database
from cachetools import TTLCache

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)
_key_cache = TTLCache(maxsize=1, ttl=300)  # Cache for 5 minutes

async def get_db(request: Request) -> Database:
    return request.app.state.db

async def get_api_keys(db: Database = Depends(get_db)) -> set[str]:
    # Cache the API keys to reduce database load
    if "api_keys" not in _key_cache:
        _key_cache["api_keys"] = set(await db.get_api_keys())
    return _key_cache["api_keys"]

# Function to invalidate the cache (e.g., after adding/removing an API key)
def invalidate_api_key_cache():
    _key_cache.clear()

# Dependency to validate the API key
async def get_api_key(api_key: str = Security(api_key_header),
                      valid_keys: set[str] = Depends(get_api_keys)):
    if api_key in valid_keys:
        return api_key
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid or missing API Key")
