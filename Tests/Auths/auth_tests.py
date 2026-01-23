import pytest
from Redis.redis_manager import RedisAsyncManager
from Tests.common_test_helper import check_keys_in_redis, TEST_AUTH_MAPPINGS


redis_instance = RedisAsyncManager(database=5)

@pytest.mark.asyncio
@pytest.mark.parametrize("schedule_item", TEST_AUTH_MAPPINGS)
async def test_auths(schedule_item):
    if not schedule_item.get("auth_class", None) or not schedule_item.get("auth_active", None):
        pytest.skip()

    found, data = await check_keys_in_redis(
        cls=schedule_item["auth_class"],
        redis_instance=redis_instance,
        key_name=schedule_item["auth_key"]
    )

    if not found:
        pytest.fail(f"Auth key for {schedule_item['book_name']} not found in Redis.")