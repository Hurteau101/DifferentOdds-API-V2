import asyncio
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
from DFS.splashsports import SplashSports

from datetime import datetime, timezone
from celery.utils.log import get_task_logger
from celery import shared_task
from Redis.redis_manager import RedisManager
from asgiref.sync import async_to_sync

from Settings.dfs_model import BookData

logger = get_task_logger(__name__)


Books = {
    "underdog": {
        "class": Underdog,
        "interval": 15,
        "task": "dfs",
    },
    "prizepicks": {
        "class": Prizepicks,
        "interval": 15,
        "task": "dfs",
    },
    "betr": {
        "class": Betr,
        "interval": 15,
        "task": "dfs",
    },
    "boom": {
        "class": Boom,
        "interval": 15,
        "task": "dfs",
    },
    "dabble": {
        "class": Dabble,
        "interval": 15,
        "task": "dfs",
    },
    "drafters": {
        "class": Drafters,
        "interval": 15,
        "task": "dfs",
    },
    "draftkings_6": {
        "class": DraftKingsPickSix,
        "interval": 15,
        "task": "dfs",
    },
    "ownerbox": {
        "class": Ownerbox,
        "interval": 15,
        "task": "dfs",
    },
    "parlaye": {
        "class": Parlaye,
        "interval": 15,
        "task": "dfs",
    },
    "parlayplay": {
        "class": Parlayplay,
        "interval": 15,
        "task": "dfs",
    },
    "sleeper": {
        "class": Sleeper,
        "interval": 15,
        "task": "dfs",
    },
    "splashsports": {
        "class": SplashSports,
        "interval": 15,
        "task": "dfs",
    },
}


### COMMENT OUT BOOKS 1 BY 1 FOR TESTING TO SEE WHERE IS BREAKING

@shared_task(ignore_result=True)
def run_dfs(name: str):
    async def _run():
        redis_manager = RedisManager(db=0)

        lock_key = f"dfs_lock:{name}"
        lock = redis_manager.redis_client.lock(lock_key, timeout=120, blocking_timeout=1)

        if not await lock.acquire(blocking=False):
            logger.info(f"Skipping DFS book {name}, already running.")
            return

        try:
            logger.info(f"Starting DFS book: {name}")
            cls = Books[name]["class"]
            book = cls()

            data = await book.run_book()

            book_data = BookData(
                last_refresh=datetime.now(timezone.utc),
                data=data if data else None,
            )

            # Back up incase no data is found, and the original data is stale and not caught earlier on.
            if book_data.data is None or len(book_data.data) == 0:
                await redis_manager.delete(f"dfs:{name}")
                return

            # await redis_manager.store_data(f"dfs:{name}", book_data.model_dump_json())
            await redis_manager.store_data(f"dfs:{name}", book_data.model_dump())

            logger.info(f"Finished DFS book: {name}")
        finally:
            try:
                await lock.release()
            except Exception:
                pass

    async_to_sync(_run)()

