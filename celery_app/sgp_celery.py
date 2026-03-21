import time
import asyncio
from datetime import timedelta
import redis
from asgiref.sync import async_to_sync
from celery import Celery, shared_task
from Auto_SGP.runner import AutoSGP

LOCK_KEY = "auto_sgp_running"
r = redis.Redis(host="localhost", port=6379, db=13)

celery_app = Celery(
    "notify_user_celery",
    broker="redis://localhost:6379/14",
    backend="redis://localhost:6379/15",
)

celery_app.conf.update(
    worker_max_tasks_per_child=1,
)

celery_app.conf.beat_schedule = {
    "run_autosgp": {
        "task": "celery_app.autosgp_tasks.run_autosgp",
        "schedule": timedelta(seconds=120),
        "options": {"expires": 3600},
    },
}

async def run_sgp():
    autosgp = await AutoSGP.create()
    await autosgp.runner()


@celery_app.task(name="celery_app.autosgp_tasks.run_autosgp")
def run_autosgp():

    # Try to acquire lock
    if not r.set(LOCK_KEY, "1", nx=True, ex=3600):
        print("Auto SGP already running — skipping.")
        return

    start_time = time.perf_counter()

    try:
        async_to_sync(run_sgp)()

        elapsed_time = time.perf_counter() - start_time
        print(f"<><><> Full Parlay Process Took: {elapsed_time:.2f} seconds <><><>")

    finally:
        r.delete(LOCK_KEY)