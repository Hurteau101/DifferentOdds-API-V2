from datetime import timedelta

beat_schedule = {
    "run-autosgp": {
        "task": "celery_app.autosgp_tasks.run_autosgp",
        "schedule": timedelta(seconds=120),
        "options": {"expires": 3600},
    }
}