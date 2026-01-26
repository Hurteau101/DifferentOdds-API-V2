import os
from Cron_Jobs.store_static import store_static
from Redis.redis_manager import static_mapping_service
import pytest
from Books.DFS.underdog import Underdog
from Books.DFS.betr import Betr
from Books.DFS.boom import Boom
from Books.DFS.chalkboard import Chalkboard
from Books.DFS.dabble import Dabble
from Books.DFS.draftkings_6 import DraftKingsPickSix
from Books.DFS.drafters import Drafters
from Books.DFS.splashsports import SplashSports
from Books.DFS.epicks import Epicks
from Books.DFS.ownerbox import Ownerbox
from Books.DFS.sleeper import Sleeper
from Books.DFS.prizepicks import Prizepicks
from Books.DFS.parlaye import Parlaye
from Books.DFS.parlayplay import Parlayplay
from Books.DFS.fanduel_picks import FanDuelPicks
from Utils.helpers import serialize_data
from Database.database import Database
from Redis.redis_manager import RedisAsyncManager
from Tests.common_test_helper import create_json_file

STATIC_MAPPING = static_mapping_service.get()

DFS_BOOKS = [
    { "book_name": "underdog", "book_cls": Underdog, "save_json": True },
    { "book_name": "betr", "book_cls": Betr, "save_json": True },
    { "book_name": "boom", "book_cls": Boom, "save_json": True },
    { "book_name": "chalkboard", "book_cls": Chalkboard, "save_json": True },
    { "book_name": "dabble", "book_cls": Dabble, "save_json": True },
    { "book_name": "draftkings_6", "book_cls": DraftKingsPickSix, "save_json": True },
    { "book_name": "drafters", "book_cls": Drafters, "save_json": True },
    { "book_name": "epicks", "book_cls": Epicks, "save_json": True },
    { "book_name": "splashsports", "book_cls": SplashSports, "save_json": True },
    { "book_name": "ownerbox", "book_cls": Ownerbox, "save_json": True },
    { "book_name": "sleeper", "book_cls": Sleeper, "save_json": True },
    { "book_name": "prizepicks", "book_cls": Prizepicks, "save_json": True },
    { "book_name": "parlaye", "book_cls": Parlaye, "save_json": True },
    { "book_name": "parlayplay", "book_cls": Parlayplay, "save_json": True },
    { "book_name": "fanduel_picks", "book_cls": FanDuelPicks, "save_json": True },
]


tables = ["stat_mapper", "league_mapper"]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dfs_items",
    DFS_BOOKS,
    ids=lambda item: (item.get("book_name") or "unknown"),
)

async def test_dfs_books(dfs_items, redis_static_mapper):
    async def _run_static():
        db = Database()
        for table in tables:
            await store_static(database_instance=db, table_name=table, redis_instance=redis_static_mapper)


    if not STATIC_MAPPING.get("leagues") or not STATIC_MAPPING.get("stats"):
        await _run_static()

    book = dfs_items.get("book_cls")()

    returned_data = await book.run_book()

    book_name = dfs_items.get("book_name")

    if not returned_data:
        pytest.fail(f"No data returned from {book_name}")

    if dfs_items.get("save_json"):
        current_directory = os.path.dirname(os.path.realpath(__file__))
        serialized_data = serialize_data(returned_data)
        create_json_file(current_directory, book_name, serialized_data)

