import os
from Tests.common_test_helper import check_keys_in_redis, create_json_file, TEST_MAPPER_BOOKS, AUTH_BOOK_BY_NAME
import pytest

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "schedule_item",
    [
        book for book in TEST_MAPPER_BOOKS
        if book.get("active") is True
    ],
    ids=lambda item: (item.get("book_name") or "unknown"),
)
async def test_mappers(schedule_item, redis_mapper, redis_auth):
    mapper_cls = schedule_item.get("mapper_class")
    mapper_key = schedule_item.get("mapper_key")
    book_name = schedule_item.get("book_name") or "unknown"

    if not mapper_cls or not mapper_key:
        pytest.skip(f"{book_name}: mapper not configured (missing mapper_class/mapper_key).")

    auth_key = AUTH_BOOK_BY_NAME.get(book_name)

    if auth_key and auth_key.get("active") is True:
        auth_key = auth_key.get("auth_key")
        if auth_key:
            auth_token_found = await redis_auth.get_data(key_name=auth_key)
            if not auth_token_found:
                pytest.fail(f"Auth key for {book_name} not found in Redis. Mapper test cannot proceed.")

    found, data = await check_keys_in_redis(
        cls=schedule_item["mapper_class"],
        redis_instance=redis_mapper,
        key_name=schedule_item["mapper_key"]
    )

    if not found:
        pytest.fail(f"Mapper key for {schedule_item['book_name']} not found in Redis. Failed to store mapped IDs.")

    if schedule_item.get("store_json", None):
        current_directory = os.path.dirname(os.path.realpath(__file__))

        create_json_file(
            current_directory=current_directory,
            book_name=schedule_item["book_name"],
            returned_data=data
        )



