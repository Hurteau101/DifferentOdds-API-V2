import time
import redis
from asgiref.sync import async_to_sync
from celery import shared_task
from Auto_SGP.runner import AutoSGP

LOCK_KEY = "auto_sgp_running"
r = redis.Redis(host="localhost", port=6379, db=13)


async def run_sgp():
    autosgp = await AutoSGP.create()
    await autosgp.runner()


@shared_task(name="SGP_Celery.sgp_worker.run_autosgp")
def run_autosgp():

    # Try to acquire lock
    if not r.set(LOCK_KEY, "1", nx=True, ex=120):
        print("Auto SGP already running — skipping.")
        return

    start_time = time.perf_counter()

    try:
        async_to_sync(run_sgp)()

        elapsed_time = time.perf_counter() - start_time
        print(f"<><><> Full Parlay Process Took: {elapsed_time:.2f} seconds <><><>")

    finally:
        r.delete(LOCK_KEY)