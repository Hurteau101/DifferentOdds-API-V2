import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


import pytest_asyncio
from Redis.redis_manager import RedisAsyncManager

# Pytest auto-discovers fixtures from conftest.py.
# Tests can request these by name (e.g. `redis_auth`) without importing anything.


@pytest_asyncio.fixture
async def redis_mapper():
    redis_instance = RedisAsyncManager(database=2)
    yield redis_instance

@pytest_asyncio.fixture
async def redis_auth():
    redis_instance = RedisAsyncManager(database=5)
    yield redis_instance

@pytest_asyncio.fixture
async def redis_static_mapper():
    redis_instance = RedisAsyncManager(database=11)
    yield redis_instance