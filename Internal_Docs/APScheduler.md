# APScheduler Breakdown

**Quick Overview:**
- Scheduler to store Auth Keys and Mapping Ids which some sportsbooks require. These keys are stored in Redis.

---

## Files

### `base_scheduler.py`
The base scheduler class.

### `scheduler_runner.py`
The scheduler runner class. 
- It is in charge of running the scheduler. It will store the Auth and Mapping needed for many books
- It contains 2 lists, one for Auths and one for Mapping. Each list contains a similar structure. If you don't want a 
book to run, you will set the `is_active` to `False`
- Whenever adding a new value to either list, ensure to add a new job to `Cron_Jobs/apscheduler_heartbeat.py`. As this cron job acts like a mini heartbeat, 
to ensure all APScheduler jobs are storing keys in Redis.

---

## Running the scheduler
- `python -m APScheduler.scheduler_runner`