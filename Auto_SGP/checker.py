import asyncio

from Auto_SGP.runner import AutoSGP
from Redis.redis_manager import RedisAsyncManager
from Auto_SGP.settings import BOOKS
from deepdiff import DeepDiff

class Checker:
    def __init__(self, autosgp: AutoSGP):
        self.autosgp = autosgp

    async def remover(self, previously_sent: set, endpoint: set):
        await self.autosgp.previously_stored_redis_instance.delete_keys(
            keys=previously_sent,
            redis_client=self.autosgp.previously_stored_redis_instance.redis_client
        )

        await self.autosgp.endpoint_redis.delete_keys(
            keys=endpoint,
            redis_client=self.autosgp.endpoint_redis.redis_client
        )


    async def run_checker(self):
        redis_previously_stored_instance = RedisAsyncManager(database=10)
        sportsbook_data = self.autosgp.load_sportsbook_data()

        previous_data = await redis_previously_stored_instance.get_all_key_values()

        if not sportsbook_data or not previous_data:
            return

        valid_sgp_books = set(
            book_name
            for book_name, book_data in BOOKS.items()
            if book_data.get("active")
        )

        previously_sent = set()
        endpoint = set()

        for market in previous_data:
            for key, odds in market.get("raw_odds", {}).items():
                previously_sent_key = market.get("key_mapper", {}).get(key)
                endpoint_key = market.get("redis_key")

                bettorodds_data = sportsbook_data.get(key)
                if not bettorodds_data:
                    print("No BettorOdds Data for Key: ", key)
                    previously_sent.add(previously_sent_key)
                    endpoint.add(endpoint_key)
                    continue

                bettorodds_odds = self.autosgp.normalize_book_odds(bettorodds_data, valid_sgp_books)
                compared_odds = DeepDiff(odds, bettorodds_odds)
                if compared_odds.get("values_changed", {}):
                    previously_sent.add(previously_sent_key)
                    endpoint.add(endpoint_key)
                    continue

        print(f"Previously Sent Keys to Remove: {previously_sent}")
        print(f"Endpoint Keys to Remove: {endpoint}")
        await self.remover(previously_sent, endpoint)


if __name__ == "__main__":
    async def main():
        autosgp = await AutoSGP.create()
        checker = Checker(autosgp)
        await checker.run_checker()

    asyncio.run(main())