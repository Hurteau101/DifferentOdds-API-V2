import asyncio

from DFS.fanduel_picks import FanDuelPicks
from DFS.prizepicks import Prizepicks
from DFS.underdog import Underdog
from DFS.betr import Betr
from DFS.boom import Boom
from DFS.dabble import Dabble
from DFS.drafters import Drafters
from DFS.draftkings_6 import DraftKingsPickSix
from DFS.ownerbox import Ownerbox
from DFS.parlaye import Parlaye
from DFS.parlayplay import Parlayplay
from DFS.sleeper import Sleeper
from DFS.epicks import Epicks
from DFS.splashsports import SplashSports

from datetime import datetime, timezone
from celery.utils.log import get_task_logger
from celery import shared_task

# from Exchange.kalashi import Kalashi
from Redis.redis_manager import RedisManager
from asgiref.sync import async_to_sync

from SGP.betmgm import BetMGM_SGP
from SGP.fanduel import Fanduel_SGP
from SGP.onyx import Onyx_SGP
from Settings.Auth_Automation.fanduel_picks_auth import generate_fanduel_picks_auth_token
from Settings.Auth_Automation.onyx_sgp_auth import generate_onyx_auth_token
from Settings.Auth_Automation.ownerbox_auth import generate_ownerbox_auth_token
from Settings.dfs_model import BookData

logger = get_task_logger(__name__)


DFS_Books = {
    "underdog": {
        "class": Underdog,
        "interval": 45,
        "task": "dfs",
    },
    "prizepicks": {
        "class": Prizepicks,
        "interval": 45,
        "task": "dfs",
    },
    "betr": {
        "class": Betr,
        "interval": 45,
        "task": "dfs",
    },
    "boom": {
        "class": Boom,
        "interval": 45,
        "task": "dfs",
    },
    "dabble": {
        "class": Dabble,
        "interval": 45,
        "task": "dfs",
    },
    "drafters": {
        "class": Drafters,
        "interval": 45,
        "task": "dfs",
    },
    # "draftkings_6": {
    #     "class": DraftKingsPickSix,
    #     "interval": 45,
    #     "task": "dfs",
    # },
    "ownerbox": {
        "class": Ownerbox,
        "interval": 45,
        "task": "dfs",
    },
    "parlaye": {
        "class": Parlaye,
        "interval": 45,
        "task": "dfs",
    },
    "parlayplay": {
        "class": Parlayplay,
        "interval": 45,
        "task": "dfs",
    },
    "sleeper": {
        "class": Sleeper,
        "interval": 45,
        "task": "dfs",
    },
    "fanduel_picks": {
        "class": FanDuelPicks,
        "interval": 45,
        "task": "dfs",
    },
    "epicks": {
        "class": Epicks,
        "interval": 45,
        "task": "dfs",
    }
    # Disabled until working fix can be found - VPN Issue.
    # "splashsports": {
    #     "class": SplashSports,
    #     "interval": 15,
    #     "task": "dfs",
    # },
}

# EXCHANGE_BOOKS = {
#     "kalashi" :{
#         "class": Kalashi,
#         "interval": 15,
#         "task": "exchange",
#     }
# }

BOOKS = {
    "dfs": DFS_Books,
    "exchange": {},
}

### COMMENT OUT BOOKS 1 BY 1 FOR TESTING TO SEE WHERE IS BREAKING
@shared_task(ignore_result=True)
def refresh_auths():
    async def _run():
        try:
            await generate_onyx_auth_token()
        except Exception as e:
            logger.error(f"Error generating Onyx auth token: {e}")
        try:
            await generate_fanduel_picks_auth_token()
        except Exception as e:
            logger.error(f"Error generating Fanduel Picks auth token: {e}")
        try:
            await generate_ownerbox_auth_token()
        except Exception as e:
            logger.error(f"Error generating Ownerbox auth token: {e}")

    async_to_sync(_run)()

@shared_task(ignore_result=True)
def map_sgp_ids():
    async def _run():
        try:
            fanduel = Fanduel_SGP(links=[])
            await fanduel.store_fanduel_data()
        except Exception as e:
            logger.error(f"Error initializing Fanduel_SGP: {e}")

        try:
            onyx = Onyx_SGP(links=[])
            await onyx.store_onyx_data()
        except Exception as e:
            logger.error(f"Error initializing Onyx_SGP: {e}")

        try:
            betmgm = BetMGM_SGP(links=[])
            await betmgm.store_betmgm_data()
        except Exception as e:
            logger.error(f"Error initializing BetMGM_SGP: {e}")


    async_to_sync(_run)()



@shared_task(ignore_result=True)
def run_book(name, redis_db, run_book_type):
    async def _run():
        redis_manager = RedisManager(db=redis_db)

        lock_key = f"{run_book_type}_lock:{name}"
        lock = redis_manager.redis_client.lock(lock_key, timeout=120, blocking_timeout=1)

        if not await lock.acquire(blocking=False):
            logger.info(f"Skipping {run_book_type} book {name}, already running.")
            return

        try:
            logger.info(f"Starting {run_book_type} book: {name}")
            cls = BOOKS[run_book_type][name]["class"]
            book = cls()

            data = await book.run_book()
            if data:
                book_data = BookData(
                    last_refresh=datetime.now(timezone.utc),
                    data=data if data else [],
                )

                # await redis_manager.store_data(f"dfs:{name}", book_data.model_dump_json())
                await redis_manager.store_data(f"{run_book_type}:{name}", book_data.model_dump(), key_expiration=300)
            # else:
            #     logger.warning(f"No data found for {run_book_type} book {name}, deleting existing data.")
            #     await redis_manager.delete(f"{run_book_type}:{name}")
            #     return

            logger.info(f"Finished {run_book_type} book: {name}")
        except Exception as e:
            logger.error(f"Error in {run_book_type} book {name}: {e}", exc_info=True)
        finally:
            try:
                await lock.release()
            except Exception as e:
                logger.error(f"Error releasing lock for {run_book_type} book {name}: {e}")

    async_to_sync(_run)()
#
#
# @shared_task(ignore_result=True)
# def run_dfs(name: str):
#     async def _run():
#         redis_manager = RedisManager(db=0)
#
#         lock_key = f"dfs_lock:{name}"
#         lock = redis_manager.redis_client.lock(lock_key, timeout=120, blocking_timeout=1)
#
#         if not await lock.acquire(blocking=False):
#             logger.info(f"Skipping DFS book {name}, already running.")
#             return
#
#         try:
#             logger.info(f"Starting DFS book: {name}")
#             cls = DFS_Books[name]["class"]
#             book = cls()
#
#             data = await book.run_book()
#
#             book_data = BookData(
#                 last_refresh=datetime.now(timezone.utc),
#                 data=data if data else [],
#             )
#
#             # Back up incase no data is found, and the original data is stale and not caught earlier on.
#             if book_data.data is None or len(book_data.data) == 0:
#                 await redis_manager.delete(f"dfs:{name}")
#                 return
#
#             # await redis_manager.store_data(f"dfs:{name}", book_data.model_dump_json())
#             await redis_manager.store_data(f"dfs:{name}", book_data.model_dump())
#
#             logger.info(f"Finished DFS book: {name}")
#         finally:
#             try:
#                 await lock.release()
#             except Exception:
#                 pass
#
#     async_to_sync(_run)()

