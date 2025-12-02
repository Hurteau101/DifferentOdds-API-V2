import asyncio
from datetime import datetime, timezone
from dataclasses import asdict

from API.Formatters.dfs_formatter import get_formatter
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
from Redis.redis_manager import RedisManager
from Settings.dfs_model import BookData
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
    "draftkings_6": {
        "class": DraftKingsPickSix,
        "interval": 45,
        "task": "dfs",
    },
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
}

redis_manager = RedisManager(db=0)

async def dfs_run_book(name, cls):
    lock_key = f"dfs_lock:{name}"
    lock = redis_manager.redis_client.lock(lock_key, timeout=60)

    got_lock = await lock.acquire(blocking=False)
    if not got_lock:
        print(f"Skipping {name}: lock already acquired")
        return

    try:
        book = cls()
        data = await book.run_book()
        if data:
            book_data = BookData(
                last_refresh=datetime.now(timezone.utc),
                data=data if data else [],
            )

            normalized_data = [asdict(player_data) for player_data in book_data.data]

            formatted = {
                "base": {
                    "last_refresh": datetime.now(timezone.utc).isoformat(),
                    "data": get_formatter("base", normalized_data)
                },
                "game": get_formatter("game", normalized_data),
            }

            for fmt, val in formatted.items():
                key = f"dfs:{name}:{fmt}"
                await redis_manager.store_data(key, val, key_expiration=600)

    except Exception as e:
        print(f"Error running {name}: {e}")
    finally:
        try:
            await lock.release()
        except Exception:
            pass


def start_scheduler():
    scheduler = AsyncIOScheduler()
    for book_name, info in DFS_Books.items():
        cls = info["class"]
        interval = info["interval"]

        scheduler.add_job(
            dfs_run_book,
            trigger="interval",
            seconds=interval,
            args=[book_name, cls],
            id=f"dfs_{book_name}_job",
            max_instances=1,
        )

    async def runner():
        scheduler.start()
        print("Async DFS Scheduler started.")
        await asyncio.Event().wait()

    asyncio.run(runner())

if __name__ == "__main__":
    start_scheduler()