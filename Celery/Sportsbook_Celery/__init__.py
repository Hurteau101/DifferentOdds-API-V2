from Monitoring.monitoring import init_sentry
init_sentry()

from celery import Celery

celery_app = Celery(
    "sportsbook_celery",
    broker="redis://localhost:6379/15",
    backend="redis://localhost:6379/16",
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_soft_time_limit=90,
    task_time_limit=180,
    worker_max_tasks_per_child=50,
    worker_prefetch_multiplier=1,
)

celery_app.conf.result_expires = 3600

app = celery_app
celery_app.autodiscover_tasks(["Sportsbook_Celery"])
