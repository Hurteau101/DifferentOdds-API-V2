import json
from datetime import datetime
import aiohttp
from Authentication.chalkboard_auth import ChalkboardAuth
from Authentication.fanduel_picks_auth import FanduelPicksAuth
from Authentication.fourcx_auth import FourcxAuth
from Authentication.kibl_auth import KiblAuth
from Authentication.onyx_auth import OnyxAuth
from Authentication.ownerbox_auth import OwnerboxAuth
from Book_Mapping.SGP.betmgm_mapper import BetMgmMapper
from Book_Mapping.SGP.caesar_mapper import CaesarMapper
from Book_Mapping.SGP.fanduel_mapper import FanduelMapper
from Book_Mapping.SGP.onyx_mapper import OnyxMapper
from Redis.redis_manager import RedisAsyncManager
from Authentication.caesars_auth import CaesarAuth


TEST_AUTH_BOOKS = [
    {
        "book_name": "fourcx",
        "auth_class": FourcxAuth,
        "auth_key": "4cx_auth_token",
        "active": True,
    },
    {
        "book_name": "fanduel_picks",
        "auth_class": FanduelPicksAuth,
        "auth_key": "fanduel_picks_auth_token",
        "active": True,
    },
    {
        "book_name": "caesars",
        "auth_class": CaesarAuth,
        "auth_key": "caesars_waf_token",
        "active": True,
    },
    {
        "book_name": "chalkboard",
        "auth_class": ChalkboardAuth,
        "auth_key": "chalkboard_access_token",
        "active": True,
    },
    {
        "book_name": "kibl",
        "auth_class": KiblAuth,
        "auth_key": "kibl_auth_token",
        "active": True,
        ### ADD THE MAPPING FOR THIS BOOK
    },
    {
        "book_name": "onyxodds",
        "auth_class": OnyxAuth,
        "auth_key": "onyx_auth_token",
        "active": False,
    },
    {
        "book_name": "ownerbox",
        "auth_class": OwnerboxAuth,
        "auth_key": "onyx_auth_token",
        "active": False,
    },
]


TEST_MAPPER_BOOKS = [
    {
        "book_name": "caesars",
        "mapper_class": CaesarMapper,
        "mapper_key": "caesar_mapped_ids",
        "active": True,
        "store_json": True
    },
    {
        "book_name": "onyxodds",
        "mapper_class": OnyxMapper,
        "mapper_key": "onyx_ids",
        "active": False,
        "store_json": True
    },
    {
        "book_name": "betmgm",
        "mapper_class": BetMgmMapper,
        "mapper_key": "betmgm_ids",
        "active": True,
        "store_json": True
    },
    {
        "book_name": "fanduel",
        "mapper_class": FanduelMapper,
        "mapper_key": "fanduel_ids",
        "active": True,
        "store_json": True
    },

]

AUTH_BOOK_BY_NAME = {book["book_name"]: book for book in TEST_AUTH_BOOKS if book.get("book_name")}

async def check_keys_in_redis(cls: type, redis_instance: RedisAsyncManager, key_name: str):
    """Helper function to check if auth keys are stored in Redis."""
    cls_instance = cls()

    async with aiohttp.ClientSession() as session:
        data_from_redis = await redis_instance.get_data(key_name)

        # Flush existing data to ensure test validity
        if data_from_redis:
            await redis_instance.redis_client.delete(key_name)


        await cls_instance.run_scheduler(
            session=session,
            redis_instance=redis_instance
        )

        data_from_redis = await redis_instance.get_data(key_name)
        if not data_from_redis:
            return False, None

    return True, data_from_redis


def create_json_file(current_directory: str, book_name: str, returned_data: dict | list):
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stored_data = {
        "run_time": run_time,
        book_name: returned_data
    }

    with open(f"{current_directory}/{book_name}_data.json", "w", ) as f:
        json.dump(stored_data, f, indent=2)
