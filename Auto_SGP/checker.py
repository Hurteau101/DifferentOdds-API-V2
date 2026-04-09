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

    def calculate_cent_movement(self, odds_1: float, odds_2: float, cent_movement_amount: int = 25):
        def normalize_odds(odds: float):
            """Convert everything to its distance from the 100 baseline"""
            if abs(odds) == 100:
                return 0

            return abs(odds) - 100

        # Check if we crossed the "Even" (100) line. One side is positive/underdog, the other is negative/favorite
        different_sides = (odds_1 < 0 and odds_2 > 0) or (odds_1 > 0 and odds_2 < 0)

        odds_1_normalized = normalize_odds(odds_1)
        odds_2_normalized = normalize_odds(odds_2)

        if different_sides:
            # If we crossed from (-) to (+), we add the distances together
            return (odds_1_normalized + odds_2_normalized) >= cent_movement_amount

        # If we stayed on the same side, we find the difference
        return abs(odds_1_normalized - odds_2_normalized) >= cent_movement_amount


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

        for market in previous_data[0:1]:
            for key, odds in market.get("raw_odds", {}).items():
                previously_sent_key = market.get("key_mapper", {}).get(key)
                endpoint_key = market.get("redis_key")

                bettorodds_data = sportsbook_data.get(key)

                # No data for this key, odds are likely removed. Remove data.
                if not bettorodds_data:
                    previously_sent.add(previously_sent_key)
                    endpoint.add(endpoint_key)
                    continue

                bettorodds_odds = self.autosgp.normalize_book_odds(bettorodds_data, valid_sgp_books)
                compared_odds = DeepDiff(odds, bettorodds_odds)

                if compared_odds.get("values_changed", {}):
                    for value_key_name, change in compared_odds["values_changed"].items():
                        old_value = change.get("old_value")
                        new_value = change.get("new_value")

                        if self.calculate_cent_movement(old_value, new_value):
                            print(f"Cent Movement Detected for Key {key}: Old Value: {old_value}, New Value: {new_value}")
                            previously_sent.add(previously_sent_key)
                            endpoint.add(endpoint_key)
                            break

        await self.remover(previously_sent, endpoint)


if __name__ == "__main__":
    async def main():
        autosgp = await AutoSGP.create()
        checker = Checker(autosgp)
        await checker.run_checker()

    asyncio.run(main())