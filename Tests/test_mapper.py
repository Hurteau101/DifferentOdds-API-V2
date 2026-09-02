from Utils.helpers import get_class_instance
import pytest
from Redis.redis_manager import RedisAsyncManager
from Settings.book_configurations import BookConfiguration
import itertools

SPECIFIC_BOOKS = []

book_config = [
    BookConfiguration.get_book_info(
    book_type=book_type,
    remove_non_active=True,
    key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path", "auth_job_dict": "auth_dict", "mapper_job_dict": "mapper_dict"}
    )

    for book_type in ["dfs", "sgp", "sportsbooks", "prediction_liquidity"]
]

if SPECIFIC_BOOKS:
    book_config = [
        [book]
        for book in itertools.chain.from_iterable(book_config)
        if book.get("book_key") in SPECIFIC_BOOKS
    ]

filtered_mapper = [
    book
    for book in itertools.chain.from_iterable(book_config)
    if book.get("mapper_dict")
]

@pytest.mark.parametrize(
    "book_config",
    [book for book in filtered_mapper],
    ids=[b["book_key"] for b in filtered_mapper],
)
async def test_auth_books(book_config):
    redis_auth_manager = RedisAsyncManager(database=1)
    redis_mapper_manager = RedisAsyncManager(database=2)
    await redis_auth_manager.flush_db()
    await redis_mapper_manager.flush_db()

    auth_dict = book_config.get("auth_dict")

    if auth_dict:
        class_instance = get_class_instance(class_name=auth_dict.class_name, class_path=auth_dict.class_path)
        valid_run = await class_instance.run_auth()
        if not valid_run:
            pytest.fail(f"Auth failed for {book_config.get('book_key')}")

    mapper_dict = book_config.get("mapper_dict")
    mapper_class_instance = get_class_instance(class_name=mapper_dict.class_name, class_path=mapper_dict.class_path)

    mapper_valid_run = await mapper_class_instance.run_mapper()
    assert mapper_valid_run

    mapper_key = mapper_dict.mapper_redis_key
    mapper_token = await redis_mapper_manager.get_data(key_name=mapper_key)

    assert mapper_token