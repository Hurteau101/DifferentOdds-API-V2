from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger

from Books.DFS.sleeper import Sleeper
from Books.DFS.splashsports import SplashSports
from Books.DFS.underdog import Underdog
from Books.DFS.betr import Betr
from Books.DFS.boom import Boom
from Books.DFS.chalkboard import Chalkboard
from Books.DFS.dabble import Dabble
from Books.DFS.drafters import Drafters
from Books.DFS.draftkings_6 import DraftKingsPickSix
from Books.DFS.epicks import Epicks
from Books.DFS.fanduel_picks import FanDuelPicks
from Books.DFS.ownerbox import Ownerbox
from Books.DFS.parlaye import Parlaye
from Books.DFS.parlayplay import Parlayplay
from Books.DFS.prizepicks import Prizepicks


from Redis.redis_manager import RedisSyncManager
import time

logger = get_task_logger(__name__)


DEFAULT_QUEUE = "sportsbook"
DEFAULT_INTERVAL = 45
DEFAULT_TIMEOUT = 120
DEFAULT_QUEUE_EXPIRATION = 120


BOOKS = {
    "underdog": {
        "class": Underdog,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "betr": {
        "class": Betr,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "boom": {
        "class": Boom,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "chalkboard": {
        "class": Chalkboard,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "dabble": {
        "class": Dabble,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "drafters": {
        "class": Drafters,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "pick_6": {
        "class": DraftKingsPickSix,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "epicks": {
        "class": Epicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "fanduel_picks": {
        "class": FanDuelPicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "ownerbox": {
        "class": Ownerbox,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": False,
    },
    "parlaye": {
        "class": Parlaye,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "parlayplay": {
        "class": Parlayplay,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "prizepicks": {
        "class": Prizepicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "sleeper": {
        "class": Sleeper,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": True,
    },
    "splashsports": {
        "class": SplashSports,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "queue": DEFAULT_QUEUE,
        "queue_expiration": DEFAULT_QUEUE_EXPIRATION,
        "type": "dfs",
        "task": "celery_app.tasks.run_sportsbooks",
        "is_active": False,
    },
}


async def _run_books(book_name: str, lock_timeout: int):
    redis_instance = RedisSyncManager(database=10)
    lock_key = f"{book_name}_lock"
    lock = redis_instance.redis_client.lock(lock_key, timeout=lock_timeout, blocking_timeout=3)

    if not lock.acquire(blocking=False):
        logger.info(f"Could not acquire lock for {book_name}. Another instance may be running.")
        return

    start_time = time.perf_counter()
    # logger.info(f"Starting task for book: {book_name.title()}")

    logger.info(
        "\n"
        "========================================\n"
        f"-> STARTING BOOK: {book_name.upper()}\n"
        "========================================"
    )
    cls = BOOKS[book_name]["class"]()
    await cls.run_book()

    lock.release()
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    # logger.info(f"{book_name.title()} finished in: {elapsed_time:.4f} seconds")

    logger.info(
        "\n"
        "========================================\n"
        f"-> COMPLETED BOOK: {book_name.upper()}\n"
        f"->  DURATION: {elapsed_time:.4f} seconds\n"
        "========================================"
    )

@shared_task(name="celery_app.tasks.run_sportsbooks")
def run_sportsbooks(book_name: str, lock_timeout):
    async_to_sync(_run_books)(book_name, lock_timeout)




