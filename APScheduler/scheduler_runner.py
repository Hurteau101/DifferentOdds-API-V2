from External_Book_Mapping.SGP.betway_mapper import BetwayMapper
from External_Book_Mapping.Sportsbooks.kibl_mapper import KiblMapper
from Monitoring.monitoring import init_sentry
init_sentry()

from External_Book_Mapping.SGP.caesar_mapper import CaesarMapper
from External_Book_Mapping.SGP.fanduel_mapper import FanduelMapper
from External_Book_Mapping.SGP.onyx_mapper import OnyxMapper
from Authentication.chalkboard_auth import ChalkboardAuth
from Authentication.kibl_auth import KiblAuth
from Authentication.onyx_auth import OnyxAuth
from Authentication.ownerbox_auth import OwnerboxAuth
from External_Book_Mapping.SGP.betmgm_mapper import BetMgmMapper
import asyncio
import logging
from datetime import datetime
from enum import Enum
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from Redis.redis_manager import RedisAsyncManager
from Authentication.caesars_auth import CaesarAuth
from Authentication.fourcx_auth import FourcxAuth
from Authentication.fanduel_picks_auth import FanduelPicksAuth

logging.basicConfig(level=logging.INFO)
logging.info("Scheduler starting...")


######### IMPORTANT #########
# Whenever adding a new job, ensure you add to the Cron_Jobs/apscheduler_heartbeat.py monitoring file as well.
#############################

class RedisSelector(Enum):
    AUTH = 5
    MAPPER = 2

AUTH_JOBS = [
    {
        "book_name": "fourcx",
        "class": FourcxAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 86400,  # 24 hours
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "fanduel_picks",
        "class": FanduelPicksAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 39600, # 11 hours
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "caesars",
        "class": CaesarAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 600, # 10 minutes
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "chalkboard",
        "class": ChalkboardAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 3600,  # 1 hour
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "kibl",
        "class": KiblAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 82800,  # 23 hours
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "onyx",
        "class": OnyxAuth,
        "job_type": "auth",
        "is_active": False,
        "interval": 18000,  # 5 hours
        "redis_db": RedisSelector.AUTH
    },
    {
        "book_name": "ownerbox",
        "class": OwnerboxAuth,
        "job_type": "auth",
        "is_active": False,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.AUTH
    },
]

MAPPER_JOBS = [
    {
        "book_name": "betmgm",
        "class": BetMgmMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 5 minutes
        "redis_db": RedisSelector.MAPPER
    },
    {
        "book_name": "caesars",
        "class": CaesarMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER
    },
    {
        "book_name": "fanduel",
        "class": FanduelMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER
    },
    {
        "book_name": "onyxodds",
        "class": OnyxMapper,
        "job_type": "mapper",
        "is_active": False,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER
    },
    {
        "book_name": "kibl",
        "class": KiblMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 86400,  # 24 Hours
        "redis_db": RedisSelector.MAPPER
    },
    {
        "book_name": "betway",
        "class": BetwayMapper,
        "job_type": "mapper",
        "is_active": False,
        "interval": 600,  # 10 Minutes
        "redis_db": RedisSelector.MAPPER
    },
]


SCHEDULES = AUTH_JOBS + MAPPER_JOBS


class ScheduleRunner:
    async def run_one(self, cls, client_session, redis_instance):
        logging.info("========================================")
        logging.info(f"-> STARTING AUTH BOOK: {cls.__name__}")
        instance = cls()
        await instance.run_scheduler(session=client_session, redis_instance=redis_instance)
        logging.info(f"-> FINISHED AUTH BOOK: {cls.__name__}")
        logging.info("========================================\n")

    async def start(self):
        redis_instances = {
            RedisSelector.AUTH: RedisAsyncManager(database=RedisSelector.AUTH.value),
            RedisSelector.MAPPER: RedisAsyncManager(database=RedisSelector.MAPPER.value),
        }

        async with aiohttp.ClientSession() as session:
            scheduler = AsyncIOScheduler()
            for schedule in SCHEDULES:
                if schedule["is_active"]:
                    scheduler.add_job(
                        self.run_one,
                        trigger=IntervalTrigger(seconds=schedule["interval"]),
                        name=f"{schedule['book_name']}_{schedule['job_type']}_job",
                        coalesce=True, # Skip missed runs
                        max_instances=1,
                        next_run_time=datetime.now(),  # Run immediately on start
                        kwargs={
                            "cls": schedule["class"],
                            "client_session": session,
                            "redis_instance": redis_instances[schedule["redis_db"]],
                        },
                        misfire_grace_time=300,
                    )

            scheduler.start()
            await asyncio.Event().wait()


if __name__ == "__main__":
    runner = ScheduleRunner()
    asyncio.run(runner.start())


