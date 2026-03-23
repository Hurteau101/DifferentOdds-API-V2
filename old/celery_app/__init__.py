from celery import Celery

# Create Celery app
celery_app = Celery(
    "differentodds",
    broker="redis://localhost:6379/9",
    backend="redis://localhost:6379/8",  # optional
)

# Setup Celery configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    task_soft_time_limit=90,
    task_time_limit=180,
    worker_max_tasks_per_child=50,    #
    worker_prefetch_multiplier=1,
)

# Expose the Celery app
app = celery_app

celery_app.autodiscover_tasks(["Sportsbook_Celery"])


########## RUNNING COMMANDS ##########
### LINUX ###
# celery -A Sportsbook_Celery.beat_schedule beat --loglevel=INFO
# celery -A Sportsbook_Celery.tasks worker --loglevel=INFO --concurrency=10

### WINDOWS ###
# celery -A Sportsbook_Celery.beat_schedule beat --loglevel=INFO
# celery -A Sportsbook_Celery.tasks worker --loglevel=INFO --pool=solo

#######################################