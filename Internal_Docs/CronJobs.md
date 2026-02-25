# Cron Jobs Breakdown
## Files

### `api_keys.py`
 - **Frequency**: 1 Hour
 - **Description**: This job stores API keys from the database and stores in Redis.

### `apscheduler_heartbeat.py`
 - **Frequency**: 5 Minutes
 - **Description**: This job is used to ensure all APScheduler jobs are storing keys in Redis.

### `store_static.py`
 - **Frequency**: 10 Minutes
 - **Description**: This job stores static values from the database and stores in Redis. This static values are known mapped 
league names and mapped stat types.

   