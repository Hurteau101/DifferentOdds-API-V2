import importlib
from Settings.book_configurations import BookConfiguration
import pytest
from Redis.redis_manager import RedisAsyncManager
from Tests.helper import get_class_instance

SPECIFIC_BOOKS = []

book_config = BookConfiguration.get_book_info(
    book_type="dfs",
    remove_non_active=True,
    key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path"}
)

if SPECIFIC_BOOKS:
    book_config = [book for book in book_config if book.get("book_key") in SPECIFIC_BOOKS]

@pytest.mark.parametrize(
    "book_config",
    [book for book in book_config],
    ids=[b["book_key"] for b in book_config],
)
async def test_dfs_books(book_config):
    redis_manager = RedisAsyncManager(database=0)
    await redis_manager.flush_db()

    class_instance = get_class_instance(class_name=book_config.get("class_name"), class_path=book_config.get("class_path"))
    book_data = await class_instance.run_book()

    assert book_data

    book_key = book_config.get("book_key")
    base_key = await redis_manager.get_data(f"{book_key}:base")
    base_game = await redis_manager.get_data(f"{book_key}:game")

    assert base_key and base_game


