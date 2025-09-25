from . import celery_app
from .tasks import BOOKS

beat_schedule = {}

for run_book_type, books in BOOKS.items():
    for book_name, book_info in books.items():
        if run_book_type == "dfs":
            redis_db = 0
            queue = "dfs"
        elif run_book_type == "exchange":
            redis_db = 1
            queue = "exchange"
        else:
            continue


        beat_schedule[f"run-{run_book_type}-{book_name}-every-{book_info['interval']}s"] = {
            "task": "celery_app.tasks.run_book",
            "schedule": book_info["interval"],
            "args": (book_name, redis_db, run_book_type),
            "options": {"queue": queue, "expires": book_info["interval"] * 3},
        }


beat_schedule["refresh-auths-every-12h"] = {
    "task": "celery_app.tasks.refresh_auths",
    "schedule": 60 * 60 * 12, # every 12 hours
    "options": {"queue": "auths", "expires": 60 * 60 * 12 + 300}, # expires after 12h + 5m
}

beat_schedule["map-sgp-ids-every-10m"] = {
    "task": "celery_app.tasks.map_sgp_ids",
    "schedule": 300,  # every 5 minutes
    "options": {"queue": "sgp", "expires": 600},  # expires after 10m
}

celery_app.conf.task_default_queue = "dfs"
celery_app.conf.beat_schedule = beat_schedule



# for book_name, book_info in BOOKS.items():
#     if book_info["task"] == "dfs":
#         beat_schedule[f"run-{book_name}-every-{book_info['interval']}s"] = {
#             "task": "celery_app.tasks.run_dfs",
#             "schedule": book_info["interval"],
#             "args": (book_name,),
#             "options": {"queue": "books", "expires": book_info["interval"] + 5},
#         }
#     e

# celery_app.conf.task_default_queue = "books"
# celery_app.conf.beat_schedule = beat_schedule


# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --concurrency=10