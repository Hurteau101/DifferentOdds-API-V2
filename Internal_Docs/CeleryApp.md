# Celery Breakdown
- Celery is the core of part of this application. Which involves extracting and saving data from the sportsbooks.

---

## Files
### `__init__.py`
- Sets up the celery app.
- Any celery configuration should be done here.

### `Celery/Sportsbook_Celery/sportsbook_worker.py`
- In charge of all the celery tasks. 
- If you do not want a certain sportsbook to run, you will set `is_active` to `False`
- We have 2 run book functions (`_run_books` and `run_sportsbooks`) - This is because its an Async task, so we
utilize the `async_to_sync` to ensure that celery runs the tasks properly.
- One key thing here is we are using `locks` in redis, to ensure that only one celery task is running at a time.
We use `blocking=False` to ensure that if a lock can't be aquired, its instantly returns instead of waiting.

### `Celery/Sportsbook_Celery/beat_schedule.py`
- In charge of scheduling celery tasks.

---

## Running Celery on Windows.
We will be running this in WSL (Windows Subsystem for Linux) to avoid compatibility issues with Windows.

### Setting up
1. Open `WSL`
2. cd into the project directory. 
    - Example:
      - `cd /mnt/c/Users/Devon/Desktop/Coding/Projects/Personal/DifferentOdds/DifferentOdds-API`
3. Ensure you have a virtual environment set up and activated.
    - To activate the virtual environment:
      - `source venv/bin/activate`
      - If you do not have a virtual environment set up, you can create one using:
        - `python3 -m venv venv`
        - Then activate it using the command above.
4. Install the required dependencies if you haven't already:
    - `pip install -r requirements.txt`
5. Start Redis server if it's not already running.
    - You can start Redis using the command:
      - `redis-server`
    - Make sure Redis is running on the default port `6379` or adjust your Celery configuration accordingly.
6. You may need to open separate WSL terminal windows for running the Beat scheduler, Celery workers and Redis Server.


### Starting Beat Scheduler
1. To start the Celery Beat scheduler, run the following command:
    - We are using `python -m` to ensure there are no import issues.
``` bash
    PYTHONPATH=./Celery python -m celery -A Sportsbook_Celery.beat_schedule beat --loglevel=info
```

### Starting Celery Worker
##### Running Celery Worker
2. To start the Celery Worker, run the following command:
    - We are using `python -m` to ensure there are no import issues.
    - This will start the worker to listen to the sportsbook queue.
``` bash
    PYTHONPATH=./Celery python -m celery -A Sportsbook_Celery worker --include Sportsbook_Celery.sportsbook_worker --loglevel=info
```
##### Threading Issue
If you are getting a threading issue,
```bash
  python -m celery -A Sportsbook_Celery worker --include Sportsbook_Celery.sportsbook_worker -P solo --loglevel=info
```