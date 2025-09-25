from celery import Celery
from celery.signals import worker_process_init
import asyncio
from Mapper.database import Database


# Create Celery app
celery_app = Celery(
    "differentodds",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",  # optional
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


@worker_process_init.connect
def reinit_db_pool(**kwargs):
    """
    Ensure every forked Celery worker process has its own fresh DB pool.
    """
    db = Database()
    asyncio.run(db.ensure_ready())


########## RUNNING COMMANDS ##########
### LINUX ###
# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --concurrency=10

### WINDOWS ###
# celery -A celery_app.beat_schedule beat --loglevel=INFO
# celery -A celery_app.tasks worker --loglevel=INFO --pool=solo

#######################################