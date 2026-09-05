from deepdiff import DeepDiff
from Redis.redis_manager import RedisSyncManager
import logging


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class MovementChecker:
    def __init__(self):
        pass

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

    def run_checker(self):
        previously_stored_endpoint_instance = RedisSyncManager(database=10)
        previously_stored_redis_instance = RedisSyncManager(database=9)
        bettorodds_redis_instance = RedisSyncManager(database=8)

        previous_data = previously_stored_endpoint_instance.get_all_key_values()

        if not previous_data:
            return

        bettorodds_data = bettorodds_redis_instance.get_data(key_name="bettorodds_odds") or {}

        if not bettorodds_data:
            logger.warning("No Bettorodds Data Found")
            return

        endpoint_keys = set()
        previous_stored_keys = set()

        for previous in previous_data:
            game_key = previous.get("game_key", "N/A")
            filter_name = previous.get("unique_filter_name", "N/A")

            for leg in previous.get("legs", []):
                league = leg.get("league", "N/A")
                event_name = leg.get("event", "N/A")
                leg_id = leg.get("id", "N/A")
                unique_id = f"{leg_id}__{filter_name}"

                found_event = bettorodds_data.get(league, {}).get(event_name, [])

                found_id = next((
                    event
                    for event in found_event
                    if event.get("id") == leg_id
                ), None)

                if not found_id:
                    logger.warning(f"Event: {event_name} not found in bettorodds data")
                    endpoint_keys.add(game_key)
                    previous_stored_keys.add(unique_id)
                    continue

                stored_odds = leg.get("odds", {})
                new_odds = {
                    book_name: book_data.get("american_odds")
                    for book_name, book_data in found_id.get("book_feed", {}).items()
                    if book_data.get("american_odds") != "N/A"
                }

                if not stored_odds or not new_odds:
                    continue

                compared_odds = DeepDiff(stored_odds, new_odds, ignore_order=True)

                if compared_odds.get("values_changed", {}):
                    for value_key_name, change in compared_odds["values_changed"].items():
                        old_value = change.get("old_value")
                        new_value = change.get("new_value")

                        if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
                            continue

                        if self.calculate_cent_movement(old_value, new_value):
                            logger.info(f"Cent Movement Detected for Key {leg_id}: Old Value: {old_value}, New Value: {new_value}")
                            endpoint_keys.add(game_key)
                            previous_stored_keys.add(unique_id)
                            break

        previously_stored_redis_instance.delete_keys(keys=previous_stored_keys)
        previously_stored_endpoint_instance.delete_keys(keys=endpoint_keys)



if __name__ == "__main__":
    movement = MovementChecker()
    movement.run_checker()