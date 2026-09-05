import asyncio
import os
import time
import redis
from celery import shared_task
from Auto_SGP.runner import AutoSGP

LOCK_KEY = "auto_sgp_running"
r = redis.Redis(host="localhost", port=6379, db=13)


async def run_sgp():
    autosgp = await AutoSGP.create()
    await autosgp.runner()


def lock_is_stale():
    """Check if the process holding the lock is still alive."""
    pid = r.get(LOCK_KEY)
    if not pid:
        return True
    try:
        os.kill(int(pid), 0)
        return False
    except ProcessLookupError:
        return True

@shared_task(name="SGP_Celery.sgp_worker.run_autosgp")
def run_autosgp():
    if r.exists(LOCK_KEY) and lock_is_stale():
        print("Stale lock detected — clearing.")
        r.delete(LOCK_KEY)


    if not r.set(LOCK_KEY, os.getpid(), nx=True, ex=7200):
        print("Auto SGP already running — skipping.")
        return

    start_time = time.perf_counter()

    try:
        asyncio.run(run_sgp())
        elapsed_time = time.perf_counter() - start_time
        print(f"<><><> Full Parlay Process Took: {elapsed_time:.2f} seconds <><><>")

    finally:
        r.delete(LOCK_KEY)