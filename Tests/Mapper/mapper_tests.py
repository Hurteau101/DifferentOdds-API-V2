import os
from Tests.common_test_helper import check_keys_in_redis, create_json_file, TEST_AUTH_MAPPINGS
from Redis.redis_manager import RedisAsyncManager
import pytest

redis_instance_mapper = RedisAsyncManager(database=2)
redis_instance_auth = RedisAsyncManager(database=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("schedule_item", TEST_AUTH_MAPPINGS)
async def test_auths(schedule_item):
    if not schedule_item.get("mapper_class", None) or not schedule_item.get("mapper_active", None):
        pytest.skip()

    if schedule_item.get("auth_key", None):
        auth_token_found = await redis_instance_auth.get_data(key_name=schedule_item["auth_key"])
        await redis_instance_auth.close_for_shutdown()
        if not auth_token_found:
            pytest.fail(f"Auth key for {schedule_item['book_name']} not found in Redis. Mapper test cannot proceed.")

    found, data = await check_keys_in_redis(
        cls=schedule_item["mapper_class"],
        redis_instance=redis_instance_mapper,
        key_name=schedule_item["mapper_key"]
    )

    if not found:
        pytest.fail(f"Mapper key for {schedule_item['book_name']} not found in Redis. Failed to store mapped IDs.")

    if schedule_item.get("store_json", None):
        current_directory = os.getcwd()
        create_json_file(
            current_directory=current_directory,
            book_name=schedule_item["book_name"],
            returned_data=data
        )


