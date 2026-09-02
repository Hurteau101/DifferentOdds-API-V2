from Utils.helpers import get_class_instance
import pytest
from Redis.redis_manager import RedisAsyncManager
from Settings.book_configurations import BookConfiguration
import itertools

SPECIFIC_BOOKS = []

book_config = BookConfiguration.get_book_info(
    book_type="prediction_liquidity",
    remove_non_active=True,
    key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path", "auth_job_dict": "auth_dict"}
)

if SPECIFIC_BOOKS:
    book_config = [
        book
        for book in itertools.chain.from_iterable(book_config)
        if book.get("book_key") in SPECIFIC_BOOKS
    ]


@pytest.mark.parametrize(
    "book_config",
    [book for book in book_config],
    ids=[b["book_key"] for b in book_config],
)
async def test_auth_books(book_config):
    redis_manager = RedisAsyncManager(database=0)
    redis_auth_manager = RedisAsyncManager(database=1)
    redis_mapper_manager = RedisAsyncManager(database=2)

    await redis_manager.flush_db()
    await redis_auth_manager.flush_db()
    await redis_mapper_manager.flush_db()

    auth_dict = book_config.get("auth_dict")

    if auth_dict:
        class_instance = get_class_instance(class_name=auth_dict.class_name, class_path=auth_dict.class_path)
        valid_run = await class_instance.run_auth()
        if not valid_run:
            pytest.fail(f"Auth failed for {book_config.get('book_key')}")

    book_instance = get_class_instance(class_name=book_config.get("class_name"), class_path=book_config.get("class_path"))
    book_data = await book_instance.run_book()

    assert book_data

    book_key = book_config.get("book_key")
    base_key = await redis_manager.get_data(book_key)

    assert base_key