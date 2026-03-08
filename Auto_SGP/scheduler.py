import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from Auto_SGP.runner import AutoSGP


async def run_autosgp():
    autosgp = await AutoSGP.create()
    await autosgp.runner()


async def main():
    print("Starting scheduler...")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_autosgp, IntervalTrigger(seconds=120))
    scheduler.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())