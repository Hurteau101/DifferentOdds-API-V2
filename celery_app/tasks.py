import asyncio
from celery.utils.log import get_task_logger
from celery import shared_task
from Redis.redis_manager import RedisManager
from DFS.underdog import Underdog
from asgiref.sync import async_to_sync

logger = get_task_logger(__name__)


Books = {
    "underdog": {
        "class": Underdog,
        "interval": 15,
        "task": "dfs",
    },
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
            await redis_manager.store_data(f"dfs:{name}", data)

            logger.info(f"Finished DFS book: {name}")
        finally:
            try:
                await lock.release()
            except Exception:
                pass

    async_to_sync(_run)()










# @celery_app.task(name="tasks.run_dfs", ignore_result=True)
# def run_dfs(name: str):
#     cls = Books[name]["class"]
#     book = cls()
#
#     async def main():
#         data = await book.run_book()
#         await redis_manager.store_data(f"dfs:{name}", data)
#
#     async_to_sync(main)()



# @celery_app.task(name="tasks.run_sportsbook")
# def run_sportsbook(name: str):
#     """Run Sportsbook-style book."""
#     cls = Books[name]["class"]
#     book = cls()
#     data = book.run_sportsbook()   # Sportsbook-specific method
#     redis_manager.store_data(f"sportsbook:{name}", data)
#     return f"{name} (Sportsbook) finished"




