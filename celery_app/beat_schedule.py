from . import celery_app
from .tasks import BOOKS

beat_schedule = {}

# for run_book_type, books in BOOKS.items():
#     for book_name, book_info in books.items():
#         if run_book_type == "dfs":
#             redis_db = 0
#             queue = "dfs"
#         elif run_book_type == "exchange":
#             redis_db = 1
#             queue = "exchange"
#         elif run_book_type == "pph":
#             redis_db = 6
#             queue = "pph"
#         else:
#             continue
#
#
#         beat_schedule[f"run-{run_book_type}-{book_name}-every-{book_info['interval']}s"] = {
#             "task": "celery_app.tasks.run_book",
#             "schedule": book_info["interval"],
#             "args": (book_name, redis_db, run_book_type),
#             "options": {"queue": queue, "expires": book_info["interval"] * 3},
#         }

for run_book_type, books in BOOKS.items():
    for book_name, book_info in books.items():

        if run_book_type == "dfs":
            redis_db = 0
            queue = "dfs"
            task_name = "celery_app.tasks.run_book_dfs"

        elif run_book_type == "pph":
            redis_db = 6
            queue = "pph"
            task_name = "celery_app.tasks.run_book_pph"
        elif run_book_type == "liquidity":
            redis_db = 4
            queue = "liquidity"
            task_name = "celery_app.tasks.run_book_liquidity"
        else:
            continue

        beat_schedule[f"{run_book_type}-{book_name}-every-{book_info['interval']}s"] = {
            "task": task_name,
            "schedule": book_info["interval"],
            "args": (book_name, redis_db),
            "options": {"queue": queue, "expires": book_info["interval"] * 3},
        }


beat_schedule["refresh-auths-every-6h"] = {
    "task": "celery_app.tasks.refresh_auths",
    "schedule": 60 * 60 * 6,  # every 6 hours
    "options": {"queue": "auths", "expires": 60 * 60 * 6 + 300},  # expires after 6h + 5m
}

beat_schedule["map-sgp-ids-every-10m"] = {
    "task": "celery_app.tasks.map_sgp_ids",
    "schedule": 300,  # every 5 minutes
    "options": {"queue": "sgp", "expires": 600},  # expires after 10m
}

celery_app.conf.task_default_queue = "dfs"
celery_app.conf.beat_schedule = beat_schedule