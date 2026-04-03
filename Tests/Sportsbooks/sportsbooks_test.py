import os
import pytest
from Books.Sportsbooks.bet105 import Bet105
from Books.Sportsbooks.sts import STS
from Redis.redis_manager import static_mapping_service
from Tests.common_test_helper import run_static, create_json_file
from Utils.helpers import serialize_data

STATIC_MAPPING = static_mapping_service.get()

SPORTSBOOKS_BOOKS = [
    { "book_name": "bet105", "book_cls": Bet105, "save_json": True, "active": False },
    { "book_name": "stg", "book_cls": STS, "save_json": True, "active": True },
]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sportsbooks_items",
    [sportsbook for sportsbook in SPORTSBOOKS_BOOKS if sportsbook.get("active")],
    ids=lambda item: (item.get("book_name") or "unknown"),
)
async def test_sportsbook(sportsbooks_items, redis_static_mapper):
    if not STATIC_MAPPING.get("leagues") or not STATIC_MAPPING.get("stats"):
        await run_static(redis_static_mapper)

    book_name = sportsbooks_items.get("book_name")

    book = sportsbooks_items.get("book_cls")()
    returned_data = await book.run_book()

    if not returned_data:
        pytest.fail(f"No data returned from {book_name}")

    if sportsbooks_items.get("save_json"):
        current_directory = os.path.dirname(os.path.realpath(__file__))
        serialized_data = serialize_data(returned_data)
        create_json_file(current_directory, book_name, serialized_data)