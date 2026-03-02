import asyncio
import json
from Auto_SGP.runner import AutoSGP
from Redis.redis_manager import RedisAsyncManager

"""Used to check stored data to ensure there aren't stale lines still remaining"""

### ENSURE TO REMOVE KEYS FROM ENDPOINT AS WELL.

class Checker(AutoSGP):
    pass

    async def load_previous_data(self, redis_instance: RedisAsyncManager):
        previous_data = await redis_instance.get_all_key_values()
        return self.index_previous_data(previous_data)

    async def run_checker(self):
        redis_previously_stored_instance = RedisAsyncManager(database=9)
        previous_data = await self.load_previous_data(redis_previously_stored_instance)
        if not previous_data:
            return

        with open("previous_data.json", "w") as f:
            json.dump(previous_data, f, indent=2)

if __name__ == "__main__":
    checker = Checker()
    asyncio.run(checker.run_checker())







