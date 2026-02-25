import os
import pytest
from Books.Prediction_Liquidity.fourcx import FourCX
from Books.Prediction_Liquidity.novig import Novig
from Books.Prediction_Liquidity.prophetx import Prophetx
from Redis.redis_manager import static_mapping_service
from Tests.common_test_helper import create_json_file
from Utils.helpers import serialize_data

STATIC_MAPPING = static_mapping_service.get()

PREDICTION_LIQUIDITY_BOOKS = [
    { "book_name": "4cx", "book_cls": FourCX, "save_json": True, "is_active": False },
    { "book_name": "novig", "book_cls": Novig, "save_json": True, "is_active": False },
    {"book_name": "prophetx", "book_cls": Prophetx, "save_json": True, "is_active": True},
]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prediction_liquidity_items",
    [sportsbook for sportsbook in PREDICTION_LIQUIDITY_BOOKS if sportsbook.get("is_active")],
    ids=lambda item: (item.get("book_name") or "unknown"),
)
async def test_prediction_liquidity(prediction_liquidity_items, redis_static_mapper):
    book_name = prediction_liquidity_items.get("book_name")

    book = prediction_liquidity_items.get("book_cls")()
    returned_data = await book.run_book()

    if not returned_data:
        pytest.fail(f"No data returned from {book_name}")

    if prediction_liquidity_items.get("save_json"):
        current_directory = os.path.dirname(os.path.realpath(__file__))
        serialized_data = serialize_data(returned_data)
        create_json_file(current_directory, book_name, serialized_data)