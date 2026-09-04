from celery import Celery

celery_app = Celery(
    "sgp_celery",
    broker="redis://localhost:6379/13",
    backend="redis://localhost:6379/14",
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=1,
)

app = celery_app
celery_app.autodiscover_tasks(["SGP_Celery"])