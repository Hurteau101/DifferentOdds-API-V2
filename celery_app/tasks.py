import asyncio
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from celery import shared_task

from DFS.prizepicks import Prizepicks
from Redis.redis_manager import RedisManager
from DFS.underdog import Underdog
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
    }
}

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
                data=data,
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

