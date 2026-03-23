from . import celery_app
from .sportsbook_worker import BOOKS


beat_schedule = {}


for book, book_details in BOOKS.items():
    if book_details.get("is_active"):
        beat_schedule[f"{book}-{book_details['type']}-Every-{book_details['interval']}s"] = {
            "task": book_details["task"],
            "schedule": book_details["interval"],
            "args": (book, book_details["lock_timeout"]),
            "options": {
                "expires": book_details['lock_timeout'],
                "soft_time_limit": book_details['soft_limit'],
                "time_limit": book_details['hard_limit']
            },
        }

celery_app.conf.beat_schedule = beat_schedule
