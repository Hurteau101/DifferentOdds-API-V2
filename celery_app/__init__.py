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
)

# Expose the Celery app
app = celery_app

celery_app.autodiscover_tasks(["celery_app"])


########## RUNNING COMMANDS ##########
### LINUX ###
# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --concurrency=10

### WINDOWS ###
# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --pool=solo

#######################################