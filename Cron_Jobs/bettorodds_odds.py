import logging
import time

from Monitoring.monitoring import init_sentry
init_sentry()

import requests
import os
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisSyncManager


def load_bettorodds(limit: str="all", retry_amount: int = 3):
    api_key = os.getenv("INTERNAL_BETTORODDS_API_KEY")
    if not api_key:
        logging.error("No API Key found for BettorOdds. Please set the INTERNAL_BETTORODDS_API_KEY environment variable.")
        create_sentry_message(
            tag_key="bettorodds",
            tag_value="api_key_failure",
            message="No API Key found",
            level="error"
        )
        return

    for retry_count in range(retry_amount):
        try:
            response = requests.get(url="https://api.eternity7.dev/api/dev_internal_feed",
                                    headers={"auth_token": api_key, "limit": limit}, timeout=50)

            if response.status_code == 200:
                redis_instance = RedisSyncManager(database=8)
                redis_instance.store_data(
                    key_name="bettorodds_odds",
                    data_to_store=response.json(),
                    key_expiration=120
                )

                return

        except requests.RequestException as e:
            # print("Failure in BettorOdds: ", e)
            logging.error(f"Attempt {retry_count + 1} - Failure in BettorOdds API request: {e}")

        time.sleep(2)

        if retry_count == retry_amount - 1:
            logging.error(f"Failed to retrieve data from BettorOdds after {retry_amount} attempts.")
            create_sentry_message(
                tag_key="bettorodds",
                tag_value="api_request_failure",
                message=f"Failed to retrieve data from BettorOdds after {retry_amount} attempts.",
                level="error"
            )



if __name__ == "__main__":
    load_bettorodds()