from . import celery_app
from .tasks import BOOKS


beat_schedule = {}


for book, book_details in BOOKS.items():
    if book_details.get("is_active"):
        beat_schedule[f"{book}-{book_details['type']}-Every-{book_details['interval']}s"] = {
            "task": book_details["task"],
            "schedule": book_details["interval"],
            "args": (book, book_details["lock_timeout"]),
            "options": {"queue": book_details['queue'], "expires": book_details['queue_expiration']},
        }

celery_app.conf.beat_schedule = beat_schedule
