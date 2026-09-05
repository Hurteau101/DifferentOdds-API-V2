from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from APScheduler.Other_Jobs.verification_mapping import VerificationMapping
from Settings.book_configurations import BookConfiguration
from itertools import chain
from datetime import datetime, timedelta
from Utils.helpers import get_class_instance
from loguru import logger
from APScheduler.Other_Jobs.api_keys import store_api_keys
from APScheduler.Other_Jobs.bettorodds_odds import load_bettorodds
from APScheduler.Other_Jobs.espn_mapper import ESPNMapper
from APScheduler.Other_Jobs.static_mapping import store_static_mapping
from apscheduler.events import EVENT_JOB_SUBMITTED, EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED, \
    EVENT_JOB_MAX_INSTANCES


class BaseScheduleRunner:
    def _attach_listeners(self, scheduler: AsyncIOScheduler):
        def _name(event):
            job = scheduler.get_job(event.job_id)
            return job.name if job else event.job_id

        def _submitted(event):
            logger.info("=" * 10)
            logger.info(f"-> Running {_name(event)}")

        def _executed(event):
            logger.info(f"-> Finished {_name(event)}")
            logger.info("=" * 10)

        def _error(event):
            logger.opt(exception=event.exception).error(f"-> Failed {_name(event)}")

        def _missed(event):
            logger.warning(f"-> Missed {_name(event)}, due {event.scheduled_run_time}")

        def _skipped(event):
            logger.warning(f"-> Skipped {_name(event)}, previous run still going")

        scheduler.add_listener(_submitted, EVENT_JOB_SUBMITTED)
        scheduler.add_listener(_executed, EVENT_JOB_EXECUTED)
        scheduler.add_listener(_error, EVENT_JOB_ERROR)
        scheduler.add_listener(_missed, EVENT_JOB_MISSED)
        scheduler.add_listener(_skipped, EVENT_JOB_MAX_INSTANCES)

    def _pre_book_setup(self) -> dict:
        """Configure the pre-set up by categorizing the books"""
        book_config = [
            BookConfiguration.get_book_info(
                book_type=book_type,
                remove_non_active=True,
                key_names={"name": "book_key", "base_file_path": "base_file_path", "class_name": "class_name",
                           "class_path": "class_path",
                           "auth_job_dict": "auth_dict", "mapper_job_dict": "mapper_dict"}
            )

            for book_type in ["dfs", "sgp", "sportsbooks", "prediction_liquidity"]
        ]

        modified_configs = [
            book
            for book in chain.from_iterable(book_config)
            if book.get("auth_dict") or book.get("mapper_dict")
        ]

        auth_jobs = []
        mapper_jobs = []

        keys = [ "class_name", "class_path"]

        for config in modified_configs:
            auth_dict = config.get("auth_dict")
            mapper_dict = config.get("mapper_dict")

            if auth_dict and auth_dict.job_active:
                auth_jobs.append({
                    **{key: getattr(auth_dict, key) for key in keys if key in config},
                    "scheduler": auth_dict.ap_scheduler,
                    "type": "auth",
                    "book_key": config.get("book_key"),
                })

            if mapper_dict and mapper_dict.job_active:
                mapper_jobs.append({
                    **{key: getattr(mapper_dict, key) for key in keys if key in config},
                    "scheduler": mapper_dict.ap_scheduler,
                    "type": "mapper",
                    "book_key": config.get("book_key"),
                })


        return {
            "auth_jobs": {"job_list": auth_jobs, "delay": 0},
            "mapper_jobs": {"job_list": mapper_jobs, "delay": 60},
        }

    async def run_job(self, job_dict: dict):
        book_key = job_dict["book_key"]

        book_instance = get_class_instance(class_name=job_dict.get("class_name"),
                                           class_path=job_dict.get("class_path"))

        if job_dict.get("type") == "auth":
            await book_instance.run_auth()
        elif job_dict.get("type") == "mapper":
            await book_instance.run_mapper()


    async def job_creator(self, scheduler: AsyncIOScheduler, job_dict: dict, delay: int):
        ap_scheduler = job_dict["scheduler"]

        scheduler.add_job(
            self.run_job,
            trigger=IntervalTrigger(seconds=ap_scheduler.interval),
            name=ap_scheduler.name,
            coalesce=ap_scheduler.coalesce,
            max_instances=ap_scheduler.max_instances,
            next_run_time=datetime.now() + timedelta(seconds=delay),
            kwargs={"job_dict": job_dict},
            misfire_grace_time=ap_scheduler.misfire_grace_time,
        )

    def _store_bettorodds_job(self, scheduler: AsyncIOScheduler):
        scheduler.add_job(
            load_bettorodds,
            trigger=IntervalTrigger(seconds=120),
            name="bettorodds_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now() + timedelta(minutes=3),
            misfire_grace_time=120,
        )

    def _store_static_mapping(self, scheduler: AsyncIOScheduler):
        scheduler.add_job(
            store_static_mapping,
            trigger=IntervalTrigger(seconds=900),
            name="static_mapping_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )

    def _store_cached_verification_mapping(self, scheduler: AsyncIOScheduler):
        vm = VerificationMapping()
        scheduler.add_job(
            vm.controller,
            trigger=IntervalTrigger(days=1),
            name="verification_mapping_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )

    def _store_api_key_job(self, scheduler: AsyncIOScheduler):
        scheduler.add_job(
            store_api_keys,
            trigger=IntervalTrigger(seconds=3000),
            name="api_key_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )

    def _store_espn_mapper(self, scheduler: AsyncIOScheduler):
        espn_mapper = ESPNMapper()
        scheduler.add_job(
            espn_mapper.run_mapping,
            trigger=IntervalTrigger(seconds=19800),
            name="espn_mapper_job",
            coalesce=True,
            max_instances=1,
            next_run_time=datetime.now(),
            misfire_grace_time=120,
        )


    async def run_schedule(self):
        job_dict = self._pre_book_setup()

        scheduler = AsyncIOScheduler()
        self._attach_listeners(scheduler=scheduler)

        await asyncio.gather(*[
            self.job_creator(scheduler=scheduler, job_dict=job, delay=job_data["delay"])
            for job_name, job_data in job_dict.items()
            for job in job_data["job_list"]
        ])

        self._store_api_key_job(scheduler=scheduler)
        self._store_static_mapping(scheduler=scheduler)
        self._store_espn_mapper(scheduler=scheduler)
        self._store_bettorodds_job(scheduler=scheduler)
        self._store_cached_verification_mapping(scheduler=scheduler)

        scheduler.start()

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError, Exception):
            pass
        finally:
            scheduler.shutdown(wait=False)



if __name__ == "__main__":
    import asyncio
    schedule_runner = BaseScheduleRunner()
    asyncio.run(schedule_runner.run_schedule())

