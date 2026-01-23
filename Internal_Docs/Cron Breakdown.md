# List of Cron Jobs
1. `store_static.py`
     - Frequency: 10 Minutes
     - Description: This job stores extracts static values from the database and stores in Redis.


2. `store_api_keys`
     - Frequency: 1 Hour
     - Description: This job stores API keys from the database and stores in Redis.
     - Files: `Mapping/store_static.py`


3. `auth_runner.py`
    - Frequency: 2 Minutes
    - Description: This job handles running all the required authentication.
