"""
We use this script as a make shift heartbeat for our APScheduler jobs.
If a key is missing from Redis that means the corresponding job has not run or failed. As all keys
do expire but should be replaced before expiration, missing keys indicate an issue.
"""
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from discordwebhook import Discord
from dotenv import load_dotenv

from Monitoring.monitoring import init_sentry, create_sentry_message
init_sentry()

import discordwebhook
from Redis.redis_manager import RedisAsyncManager

# No onyx or Ownerbox - Broken
## UNCOMMENT AFTER TESTING
# AUTH_KEYS = [
#     "caesars_waf_token", "fanduel_picks_auth_token", "caesars_waf_token",
#     "chalkboard_access_token", "kibl_auth_token"
# ]

AUTH_KEYS = [
    # "caesars_waf_token",
]

# No onyx - Broken

## UNCOMMENT AFTER TESTING
# MAPPER_KEYS = [
#     "betmgm_ids", "fanduel_ids", "caesar_mapped_ids", "kibl_mapper_data", "betmgm_ids"
# ]

MAPPER_KEYS = [
    # "betmgm_ids", "fanduel_ids", "caesar_mapped_ids", "betmgm_ids"
    "betmgm_ids", "fanduel_ids", "betmgm_ids"
]

### TEST DISCORD MESSAGE
load_dotenv()
webhook_url = (
    os.getenv("LOG_WEBHOOK_URL")
)
discord = Discord(url=webhook_url)
def send_discord_message(keys_missing):
    fields = [
        {
            "name": "Keys Missing",
            "value": f"Missing Keys: {', '.join(keys_missing)}",
        }
    ]

    embed = {
        "title": "APScheduler Heartbeat",
        "color": 0x2ECC71,
        "fields": fields,
        "timestamp": datetime.now(tz=ZoneInfo("America/Denver")).isoformat()
    }

    discord.post(
        embeds=[embed]
    )


async def apscheduler_heartbeat():
    print(f"Running Heartbeat... {datetime.now()}")
    redis_auth_instance = RedisAsyncManager(database=5)
    redis_mapper_instance = RedisAsyncManager(database=2)

    missing_keys = []

    for key in AUTH_KEYS:
        data = await redis_auth_instance.get_data(key_name=key)
        if not data:
            missing_keys.append(key)

    for key in MAPPER_KEYS:
        data = await redis_mapper_instance.get_data(key_name=key)
        if not data:
            missing_keys.append(key)

    if missing_keys:
        send_discord_message(missing_keys)
        create_sentry_message(
            tag_key="apscheduler_heartbeat",
            tag_value="missing_redis_keys",
            message=f"Missing keys in Redis: {', '.join(missing_keys)}",
            level="warning"
        )

    print(f"Heartbeat Complete... {datetime.now()}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(apscheduler_heartbeat())
