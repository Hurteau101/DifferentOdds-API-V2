from datetime import timedelta
from . import celery_app

beat_schedule = {
    "run-autosgp": {
        "task": "celery_app.sgp_tasks.run_autosgp",
        "schedule": timedelta(seconds=120),
        "options": {"expires": 3600},
    }
}

celery_app.conf.beat_schedule = beat_schedule