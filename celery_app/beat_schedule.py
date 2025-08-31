from . import celery_app
from .tasks import Books

beat_schedule = {}

for book_name, book_info in Books.items():
    if book_info["task"] == "dfs":
        beat_schedule[f"run-{book_name}-every-{book_info['interval']}s"] = {
            "task": "celery_app.tasks.run_dfs",
            "schedule": book_info["interval"],
            "args": (book_name,),
        }

celery_app.conf.beat_schedule = beat_schedule



# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --concurrency=10