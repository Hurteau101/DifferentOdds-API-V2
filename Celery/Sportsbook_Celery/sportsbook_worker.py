import importlib
from asgiref.sync import async_to_sync
import time
from celery import shared_task
from Redis.redis_manager import RedisSyncManager
from loguru import logger

async def _run_book(config: dict):
    redis_instance = RedisSyncManager(database=14)
    book_key = config.get("book_key")

    lock_key = f"{book_key}_lock"
    lock = redis_instance.redis_client.lock(lock_key, timeout=60, blocking_timeout=3)

    logger.info(f"-> Task Received for book: {book_key}")
    if not lock.acquire(blocking=False):
        logger.info(f"Could not acquire lock for {book_key}. Another instance may be running.")
        return

    start_time = time.perf_counter()

    try:
        module = importlib.import_module(config.get("class_path"))
        my_class = getattr(module, config.get("class_name"))
        class_instance = my_class()
        await class_instance.run_book()
    finally:
        try:
            if lock.locked():
                lock.release()
        except Exception as e:
            logger.warning(f"Error releasing lock for {book_key}: {e}")

    elapsed_time = time.perf_counter() - start_time
    logger.info(f"Task completed for book: {book_key} in {elapsed_time:.2f} seconds")

@shared_task(name="Sportsbook_Celery.sportsbook_worker.run_sportsbooks")
def run_sportsbooks(config: dict):
    async_to_sync(_run_book)(config)
