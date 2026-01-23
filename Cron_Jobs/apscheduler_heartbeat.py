"""
We use this script as a make shift heartbeat for our APScheduler jobs.
If a key is missing from Redis that means the corresponding job has not run or failed. As all keys
do expire but should be replaced before expiration, missing keys indicate an issue.
"""

from Monitoring.monitoring import init_sentry, create_sentry_message
init_sentry()

from Redis.redis_manager import RedisAsyncManager

# No onyx or Ownerbox - Broken
AUTH_KEYS = [
    "caesars_waf_token", "fanduel_picks_auth_token", "caesars_waf_token",
    "chalkboard_access_token", "kibl_auth_token"
]

# No onyx - Broken
MAPPER_KEYS = [
    "betmgm_ids", "fanduel_ids", "caesar_mapped_ids",
]


async def apscheduler_heartbeat():
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
        create_sentry_message(
            tag_key="apscheduler_heartbeat",
            tag_value="missing_redis_keys",
            message=f"Missing keys in Redis: {', '.join(missing_keys)}",
            level="warning"
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(apscheduler_heartbeat())
