from itertools import chain
from Settings.book_configurations import BookConfiguration
from . import celery_app

book_config = [
    BookConfiguration.get_book_info(
        book_type=book_type,
        remove_non_active=True,
        key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path", "celery_details": "celery_details"}
    )
    for book_type in ["dfs", "sportsbooks"]
]

beat_schedule = {}

for config in chain.from_iterable(book_config):
    book_key = config.get("book_key")
    celery_details = config.pop("celery_details")

    beat_schedule[f"{book_key}-{celery_details.book_type}-Every-{celery_details.interval}s"] = {
        "task": "Sportsbook_Celery.sportsbook_worker.run_sportsbooks",
        "schedule": celery_details.interval,
        "args": (config,),
        "options": {
            "expires": celery_details.lock_timeout,
            "soft_time_limit": celery_details.soft_limit,
            "time_limit": celery_details.hard_limit
        },
    }

celery_app.conf.beat_schedule = beat_schedule
