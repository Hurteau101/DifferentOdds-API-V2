import pytest
from Tests.common_test_helper import check_keys_in_redis, TEST_AUTH_BOOKS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "schedule_item",
    [
        book for book in TEST_AUTH_BOOKS
        if book.get("active") is True
    ],
    ids=lambda item: (item.get("book_name") or "unknown")
)


async def test_auths(schedule_item, redis_auth):
    if not schedule_item.get("auth_class", None):
        pytest.skip()

    found, data = await check_keys_in_redis(
        cls=schedule_item["auth_class"],
        redis_instance=redis_auth,
        key_name=schedule_item["auth_key"]
    )

    if not found:
        pytest.fail(f"Auth key for {schedule_item['book_name']} not found in Redis.")