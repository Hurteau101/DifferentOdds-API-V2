from External_Book_Mapping.SGP.fliff_mapper import FliffMapper
from Monitoring.monitoring import init_sentry
init_sentry()
from Authentication.buckeye1_auth import Buckeye1Auth
from Authentication.fliff_auth import FliffAuth
import os
import random
from Authentication.buckeye2_auth import Buckeye2Auth
from Authentication.metallic_auth import MetallicAuth
from Authentication.ace_auth import AceAuth
from Auto_SGP.checker import Checker
from Auto_SGP.runner import AutoSGP
import aiohttp
from External_Book_Mapping.SGP.betway_mapper import BetwayMapper
from External_Book_Mapping.Sportsbooks.kibl_mapper import KiblMapper
from External_Book_Mapping.SGP.caesar_mapper import CaesarMapper
from External_Book_Mapping.SGP.fanduel_mapper import FanduelMapper
from External_Book_Mapping.SGP.onyx_mapper import OnyxMapper
from Authentication.chalkboard_auth import ChalkboardAuth
from Authentication.kibl_auth import KiblAuth
from Authentication.onyx_auth import OnyxAuth
from Authentication.sts_auth import STSAuth
from External_Book_Mapping.SGP.betmgm_mapper import BetMgmMapper

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from curl_cffi import AsyncSession as CurlAsyncSession
from aiohttp import ClientSession as AiohttpClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from Redis.redis_manager import RedisAsyncManager
from Authentication.caesars_auth import CaesarAuth
from Authentication.fourcx_auth import FourcxAuth
from Books.Prediction_Liquidity.compare import LiquidityCompare


class RedisSelector(Enum):
    AUTH = 5
    MAPPER = 2


##### BREAKDOWN OF AUTH_JOBS & MAPPER_JOBS ######
# 'book_name' - The name of the Sportsbook. This is used for logging and monitoring purposes.
# 'class' - This is the actual class that will be instantiated and run for this job. It should have a method called 'run_scheduler' that takes in a session and a redis instance.
# 'job_type' - This is a string that indicates the type of job. This is used for logging and monitoring purposes.
# 'is_active' - This is a boolean that indicates whether the job should be scheduled or not. This allows you to easily turn on/off jobs without having to remove them from the list.
# 'interval' - This is the interval in seconds at which the job should run. For example, if you want a job to run every 10 minutes, you would set this to 600.
# 'redis_db' - This indicates which Redis database the job should use.
# 'session_type' - This indicates which type of session the job requires. This allows you to have different types of sessions (e.g., aiohttp, curl).
# 'redis_key_checker_name' - This is the name of the Redis key that should be checked after the job runs to verify that it was successful. This is used in the post-job check to ensure that the job completed successfully and that the expected data is in Redis.
# 'requires_auth' - This is a boolean that indicates whether the job requires an auth token to run. If True, the pre-job check will verify that the necessary auth token is available in Redis before allowing the job to be scheduled.
# 'redis_auth_checker_name' - If 'requires_auth' is True, this is the name of the Redis key that contains the auth token that should be checked before scheduling the job. This allows the pre-job check to verify that the required auth token is present in Redis before allowing the job to be scheduled.
######################


AUTH_JOBS = [
    {
        "book_name": "fourcx",
        "class": FourcxAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 86400,  # 24 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "4cx_auth_token",
    },
    {
        "book_name": "caesars",
        "class": CaesarAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 600, # 10 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "caesars_waf_token",
    },
    {
        "book_name": "chalkboard",
        "class": ChalkboardAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 3600,  # 1 hour
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "chalkboard_access_token",
    },
    {
        "book_name": "kibl",
        "class": KiblAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 82800,  # 23 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "kibl_auth_token",
    },
    {
        "book_name": "onyx",
        "class": OnyxAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 25200,  # 7 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "onyx_auth",
    },
    {
        "book_name": "ace",
        "class": AceAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "ace_cookies",
    },
    {
        "book_name": "metallic",
        "class": MetallicAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "metallic_token",
    },
    {
        "book_name": "buckeye2",
        "class": Buckeye2Auth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "buckeye_2_auth_token",
    },
    {
        "book_name": "sts",
        "class": STSAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "curl",
        "redis_key_checker_name": "sts_cookies",
    },
    {
        "book_name": "buckeye1",
        "class": Buckeye1Auth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "curl",
        "redis_key_checker_name": "buckeye1_cookies",
    },
    {
        "book_name": "fliff",
        "class": FliffAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 180,  # 3 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "fliff_auth_token",
    },
]

MAPPER_JOBS = [
    {
        "book_name": "betmgm",
        "class": BetMgmMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 5 minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "aiohttp",
        "requires_auth": False,
        "redis_key_checker_name": "betmgm_ids",
    },
    {
        "book_name": "caesars",
        "class": CaesarMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "curl",
        "requires_auth": True,
        "redis_key_checker_name": "caesar_mapped_ids",
        "redis_auth_checker_name": "caesars_waf_token"
    },
    {
        "book_name": "fanduel",
        "class": FanduelMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "aiohttp",
        "requires_auth": False,
        "redis_key_checker_name": "fanduel_ids"
    },
    {
        "book_name": "onyxodds",
        "class": OnyxMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "aiohttp",
        "requires_auth": True,
        "redis_key_checker_name": "onyx_ids",
        "redis_auth_checker_name": "onyx_auth"
    },
    {
        "book_name": "kibl",
        "class": KiblMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 86400,  # 24 Hours
        "redis_db": RedisSelector.MAPPER,
        "session_type": "aiohttp",
        "requires_auth": True,
        "redis_key_checker_name": "kibl_mapper_data",
        "redis_auth_checker_name": "kibl_auth_token"
    },
    {
        "book_name": "betway",
        "class": BetwayMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 Minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "curl",
        "requires_auth": False,
        "redis_key_checker_name": "betway_mapped_ids"
    },
    {
        "book_name": "fliff",
        "class": FliffMapper,
        "job_type": "mapper",
        "is_active": True,
        "interval": 600,  # 10 Minutes
        "redis_db": RedisSelector.MAPPER,
        "session_type": "aiohttp",
        "requires_auth": True,
        "redis_key_checker_name": "fliff_ids"
    },
]


class BaseSchedulerRunner:
    def __init__(self, job_list: list[dict]):
        self.job_list = job_list
        self.redis_instances = {
            RedisSelector.AUTH: RedisAsyncManager(database=RedisSelector.AUTH.value),
            RedisSelector.MAPPER: RedisAsyncManager(database=RedisSelector.MAPPER.value),
        }

    async def pre_job_check(self, job: dict) -> bool:
        return True

    async def post_job_check(self, job: dict) -> bool:
        return True

    async def schedule_creator(self, scheduler: AsyncIOScheduler, schedule: dict, run_function: callable,
                               session: [AiohttpClientSession, CurlAsyncSession], job: dict,
                               start_up_delay: int,
                               redis_instance_mapper: dict, skip_missed_runs: bool = True, max_instances: int = 1,
                               misfire_grace_time: int = 300):
        scheduler.add_job(
            run_function,
            trigger=IntervalTrigger(seconds=schedule["interval"]),
            name=f"{schedule['book_name']}_{schedule['job_type']}_job",
            coalesce=skip_missed_runs,
            max_instances=max_instances,
            next_run_time=datetime.now() + timedelta(seconds=start_up_delay),  # Run immediately on start
            kwargs={
                "cls": schedule["class"],
                "session": session,
                "redis_instance_mapper": redis_instance_mapper[schedule["redis_db"]],
                "job": job,
            },
            misfire_grace_time=misfire_grace_time,
        )

    async def run_one(self, cls: type, session: [AiohttpClientSession, CurlAsyncSession], redis_instance_mapper: dict, job: dict):
        logging.info("=" * 10)
        logging.info(f"-> STARTING: {cls.__name__}")
        instance = cls()

        for retry in range(1, 4):
            try:
               success  = await asyncio.wait_for(instance.run_scheduler(session=session, redis_instance=redis_instance_mapper), timeout=300)
               if success:
                   break
            except asyncio.TimeoutError:
                logging.error(f"Timeout: {cls.__name__} - Releasing Job")
            except Exception as e:
                logging.error(f"Error: {cls.__name__} - {e}")

            wait_time = retry * random.uniform(3, 10)
            await asyncio.sleep(wait_time)

            logging.log(logging.WARNING if retry < 3 else logging.ERROR, f"Retrying {cls.__name__} (attempt {retry}/3)...")

        logging.info(f"-> FINISHED: {cls.__name__}")
        logging.info("=" * 10 + "\n")


    async def start(self, session_dict: dict):
        scheduler = AsyncIOScheduler()

        async def schedule_if_passes(job, index):
            if not await self.pre_job_check(job):
                return

            session = session_dict.get(job["session_type"])

            if not session:
                logging.error(f"No session for {job['session_type']} required by {job['book_name']}. Skipping.")
                return

            await self.schedule_creator(
                scheduler=scheduler,
                schedule=job,
                run_function=self.run_one,
                session=session,
                redis_instance_mapper=self.redis_instances,
                job=job,
                start_up_delay=index * 15
            )

        scheduler.start()

        active_jobs = [job for job in self.job_list if job["is_active"]]

        await asyncio.gather(*[
            schedule_if_passes(job, index)
            for index, job in enumerate(active_jobs)
        ])

class AuthRunner(BaseSchedulerRunner):
    async def post_job_check(self, job: dict) -> bool:
        auth_key = job.get("redis_key_checker_name")
        token = await self.redis_instances[RedisSelector.AUTH].get_data(auth_key)
        return True if token else False


class MappingRunner(BaseSchedulerRunner):
    async def post_job_check(self, job: dict) -> bool:
        mapper_key = job.get("redis_key_checker_name")
        token = await self.redis_instances[RedisSelector.MAPPER].get_data(mapper_key)
        return True if token else False

    async def pre_job_check(self, job: dict) -> bool:
        if not job.get("requires_auth"):
            return True

        auth_key = job.get("redis_auth_checker_name")
        if not auth_key:
            logging.warning(f"No auth_key defined for {job['book_name']}. Skipping.")
            return False

        for attempt in range(12):
            token = await self.redis_instances[RedisSelector.AUTH].get_data(auth_key)

            if token:
                return True

            logging.warning(f"Auth token not found for {job['book_name']} (attempt {attempt + 1}/12). Retrying in 20s...")
            await asyncio.sleep(20)

        logging.error(f"Auth token still not available for {job['book_name']} after retries. Skipping.")
        return False


async def run_compare():
    instance = LiquidityCompare()
    await instance.run()

async def run_auto_sgp_checker():
    autosgp = await AutoSGP.create()
    checker = Checker(autosgp)
    await checker.run_checker()

async def run():
    logging.basicConfig(level=logging.INFO)
    logging.info("Scheduler starting...")

    async with CurlAsyncSession(impersonate="safari15_5") as curl_session, aiohttp.ClientSession() as aiohttp_session:
        session_dict = {"curl": curl_session, "aiohttp": aiohttp_session}
        auth_runner = AuthRunner(job_list=AUTH_JOBS)
        await auth_runner.start(session_dict=session_dict)

        map_runner = MappingRunner(job_list=MAPPER_JOBS)
        await map_runner.start(session_dict=session_dict)


        ## Prediction Liquidity Comparer
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_compare,
            trigger=IntervalTrigger(seconds=60),
            name="compare_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )

        scheduler.start()

        scheduler_checker = AsyncIOScheduler()
        scheduler_checker.add_job(
            run_auto_sgp_checker,
            trigger=IntervalTrigger(seconds=60),
            name="sgp_checker_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )

        scheduler_checker.start()

        await asyncio.Event().wait()



if __name__ == "__main__":
    asyncio.run(run())

