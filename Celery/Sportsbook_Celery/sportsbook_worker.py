from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from redis.exceptions import LockNotOwnedError

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
from Books.Prediction_Liquidity.novig import Novig
from Books.Prediction_Liquidity.prophetx import Prophetx

from Books.Sportsbooks.bet105 import Bet105
from Books.Sportsbooks.ace import Ace
from Books.Sportsbooks.buckeye_2 import Buckeye2
from Books.Sportsbooks.metalic import Metallic
from Books.Sportsbooks.onebv import OneBv
from Books.Sportsbooks.sts import STS

from Books.Prediction_Liquidity.fourcx import FourCX

from Redis.redis_manager import RedisSyncManager
import time

logger = get_task_logger(__name__)

DEFAULT_INTERVAL = 45
DEFAULT_TIMEOUT = 180

SOFT_LIMIT=120
HARD_LIMIT=160

BOOKS = {
    "underdog": {
        "class": Underdog,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "betr": {
        "class": Betr,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "boom": {
        "class": Boom,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "chalkboard": {
        "class": Chalkboard,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "dabble": {
        "class": Dabble,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "drafters": {
        "class": Drafters,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "pick_6": {
        "class": DraftKingsPickSix,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "epicks": {
        "class": Epicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "fanduel_picks": {
        "class": FanDuelPicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "ownerbox": {
        "class": Ownerbox,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "parlaye": {
        "class": Parlaye,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "parlayplay": {
        "class": Parlayplay,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "prizepicks": {
        "class": Prizepicks,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "sleeper": {
        "class": Sleeper,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "splashsports": {
        "class": SplashSports,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "dfs",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "4cx": {
        "class": FourCX,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "prediction_liquidity",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
    "soft_limit": SOFT_LIMIT,
    "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "bet105": {
        "class": Bet105,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
    "soft_limit": SOFT_LIMIT,
    "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "sts": {
        "class": STS,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
    "soft_limit": SOFT_LIMIT,
    "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "novig": {
        "class": Novig,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "prophetx": {
        "class": Prophetx,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "ace": {
        "class": Ace,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": False,
    },
    "1bv": {
        "class": OneBv,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "metallic": {
        "class": Metallic,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
    "buckeye2": {
        "class": Buckeye2,
        "interval": DEFAULT_INTERVAL,
        "lock_timeout": DEFAULT_TIMEOUT,
        "type": "sportsbook",
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "soft_limit": SOFT_LIMIT,
        "hard_limit": HARD_LIMIT,
        "is_active": True,
    },
}


async def _run_books(book_name: str, lock_timeout: int):
    redis_instance = RedisSyncManager(database=16)
    lock_key = f"{book_name}_lock"
    lock = redis_instance.redis_client.lock(lock_key, timeout=lock_timeout, blocking_timeout=3)

    logger.info(f"TASK RECEIVED book={book_name} lock_timeout={lock_timeout}")

    if not lock.acquire(blocking=False):
        logger.info(f"Could not acquire lock for {book_name}. Another instance may be running.")
        return

    start_time = time.perf_counter()

    try:
        logger.info(
            "\n"
            "========================================\n"
            f"-> STARTING BOOK: {book_name.upper()}\n"
            "========================================"
        )
        cls = BOOKS[book_name]["class"]()
        await cls.run_book()
    finally:
        try:
            if lock.locked():
                lock.release()
        except LockNotOwnedError:
            logger.warning(f"{book_name} lock expired before release.")

    elapsed_time = time.perf_counter() - start_time

    logger.info(
        "\n"
        "========================================\n"
        f"-> COMPLETED BOOK: {book_name.upper()}\n"
        f"->  DURATION: {elapsed_time:.4f} seconds\n"
        "========================================"
    )

@shared_task(name="Sportsbook_Celery.sportsbook_worker.run_sportsbooks")
def run_sportsbooks(book_name: str, lock_timeout):
    async_to_sync(_run_books)(book_name, lock_timeout)




