import asyncio
import time
from datetime import datetime, timezone
from dataclasses import asdict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
# from DFS.splashsports import SplashSports  # if/when you want it

from Redis.redis_manager import RedisManager
from Settings.dfs_model import BookData


DFS_BOOKS = {
    "underdog":      (Underdog, 45),
    "prizepicks":    (Prizepicks, 45),
    "betr":          (Betr, 45),
    "boom":          (Boom, 45),
    "dabble":        (Dabble, 45),
    "drafters":      (Drafters, 45),
    "draftkings_6":  (DraftKingsPickSix, 45),
    "ownerbox":      (Ownerbox, 45),
    "parlaye":       (Parlaye, 45),
    "parlayplay":    (Parlayplay, 45),
    "sleeper":       (Sleeper, 45),
    "fanduel_picks": (FanDuelPicks, 45),
    "epicks":        (Epicks, 45),
    # "splashsports":  (SplashSports, 45),

}

redis_manager = RedisManager(db=0)


async def dfs_run_book(name: str, cls):
    start = time.time()
    print(f"[{name}] START at {datetime.now(timezone.utc).isoformat()}")

    try:
        book = cls()
        data = await book.run_book()
        if not data:
            print(f"[{name}] No data returned")
            return

        book_data = BookData(
            last_refresh=datetime.now(timezone.utc),
            data=data,
        )
        normalized = [asdict(player_data) for player_data in book_data.data]

        formatted = {
            "base": {
                "last_refresh": datetime.now(timezone.utc).isoformat(),
                "data": get_formatter("base", normalized),
            },
            "game": get_formatter("game", normalized),
        }

        for fmt, val in formatted.items():
            key = f"dfs:{name}:{fmt}"
            await redis_manager.store_data(key, val, key_expiration=600)

        elapsed = time.time() - start
        print(f"[{name}] DONE in {elapsed:.2f}s")

    except Exception as e:
        elapsed = time.time() - start
        print(f"[{name}] ERROR after {elapsed:.2f}s: {e}")


def start_scheduler():
    async def main():
        print("[DFS] Async per-book scheduler starting…")

        scheduler = AsyncIOScheduler()

        for name, (cls, interval) in DFS_BOOKS.items():
            scheduler.add_job(
                dfs_run_book,
                trigger="interval",
                seconds=interval,
                args=[name, cls],
                id=f"dfs_{name}",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            print(f"[DFS] Registered {name} @ every {interval}s")

        scheduler.start()

        await asyncio.Event().wait()

    asyncio.run(main())


if __name__ == "__main__":
    start_scheduler()
