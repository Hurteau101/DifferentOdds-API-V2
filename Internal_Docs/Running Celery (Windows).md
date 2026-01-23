# Running Celery on Windows.
We will be running this in WSL (Windows Subsystem for Linux) to avoid compatibility issues with Windows.

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
    python -m celery -A celery_app.beat_schedule beat --loglevel=info
```

### Starting Celery Worker
##### Single Queue
2. To start the Celery Worker, run the following command:
    - We are using `python -m` to ensure there are no import issues.
    - This will start the worker to listen to the sportsbook queue.
``` bash
    python -m celery -A celery_app.celery_app worker -Q sportsbook --loglevel=info
```
##### Multiple Queues
3. To start the Celery Worker for multiple queues, run the following command:
    - We are using `python -m` to ensure there are no import issues.
    - This will start the worker to listen to the `dfs`, `exchange`, `auths`, and `sgp` queues.
``` bash
    python -m celery -A celery_app.celery_app worker -Q dfs,exchange,auths,sgp --loglevel=info
```
You can also use the `-P solo` flag to run celery in a single-threaded mode if you encounter issues with multi-threading on Windows (advisable to use this if running in IDE terminal).
``` bash
    python -m celery -A celery_app.celery_app worker -Q dfs,exchange,auths,sgp -P solo --loglevel=info
```

