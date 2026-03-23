from datetime import timedelta
from . import celery_app

celery_app.conf.beat_schedule = {
    "run_autosgp": {
        "task": "SGP_Celery.sgp_worker.run_autosgp",
        "schedule": timedelta(seconds=120),
        "options": {"expires": 3600},
    },
}