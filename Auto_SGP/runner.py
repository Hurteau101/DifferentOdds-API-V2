import asyncio
import random
from dotenv import load_dotenv
from decimal import Decimal
from Database.database import Database
from Utils.request_caller import APICaller
from curl_cffi import AsyncSession as CurlAsyncSession
from Redis.redis_manager import RedisAsyncManager, RedisSyncManager
import os
import logging
import itertools

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class AutoSGP(APICaller):
    load_dotenv()

    def __init__(self, endpoint_redis: RedisAsyncManager, configs: list, previous_redis_instance: RedisSyncManager,
                 previously_sent_discord_redis: RedisAsyncManager, redis_book_mapped_ids_instance: RedisAsyncManager,
                 redis_book_auth_instance: RedisAsyncManager, bettorodds_redis_instance: RedisSyncManager):
        super().__init__()
        self.endpoint_redis = endpoint_redis
        self.configs = configs
        self.previously_stored_redis_instance = previous_redis_instance
        self.previously_sent_discord_redis = previously_sent_discord_redis
        self.redis_book_mapped_ids_instance = redis_book_mapped_ids_instance
        self.redis_book_auth_instance = redis_book_auth_instance
        self.bettorodds_redis_instance = bettorodds_redis_instance


    @classmethod
    async def create(cls):
        """Factory method to create an instance of AutoSGP and set up configurations"""
        environment_type = os.getenv("ENVIRONMENT")

        if not environment_type:
            raise RuntimeError("Environment not set")

        production = environment_type.lower() == "production"

        db = Database()
        configs = db.get_auto_sgp_configs(is_production=production)

        if not configs:
            raise RuntimeError("Configs not found in database")

        modified_configs = [
            {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in row.items()
            }
            for row in configs
            if row.get("is_active")
        ]

        endpoint_redis = RedisAsyncManager(database=10)
        redis_previously_stored_instance = RedisSyncManager(database=9)
        previously_sent_discord_redis = RedisAsyncManager(database=12)
        redis_book_mapped_ids_instance = RedisAsyncManager(database=2)
        redis_book_auth_instance = RedisAsyncManager(database=5)
        bettorodds_redis_instance = RedisSyncManager(database=8)

        # discord_sgp = DiscordSGP(production=production)


        return cls(endpoint_redis=endpoint_redis, configs=modified_configs,
                   previous_redis_instance=redis_previously_stored_instance,
                   previously_sent_discord_redis=previously_sent_discord_redis,
                   redis_book_auth_instance=redis_book_auth_instance,
                   redis_book_mapped_ids_instance=redis_book_mapped_ids_instance,
                   bettorodds_redis_instance=bettorodds_redis_instance
                   )

    def create_slips(self, filtered_bettorodds_data: dict, stat_types: list, redis_keys: set, unique_name: str, league:str) -> list:
        slips = []

        for game_name, game_data in filtered_bettorodds_data.items():
            buckets = {stat: [] for stat in stat_types}

            for game in game_data:
                if len(game.get("book_feed")) <= 1:
                    continue

                redis_key = f"{game.get('id')}__{unique_name}"
                if redis_key in redis_keys:
                    continue

                stat = game.get("stat", '').lower()

                if stat in buckets:
                    buckets[stat].append({"event": game_name, "league": league, **game, "redis_key": redis_key})

            for bucket in buckets.values():
                random.shuffle(bucket)

            slips.extend(list(combo) for combo in zip(*buckets.values()))

        # self.previously_stored_redis_instance.bulk_insert_individual(
        #     data_to_store={
        #         slip.get("redis_key"): {
        #             "date": slip.get("date"),
        #             "game_key": slip.get("redis_key")
        #         }
        #         for slip in itertools.chain.from_iterable(slips)
        #     },
        #     pipeline=self.previously_stored_redis_instance.redis_client.pipeline()
        # )

        return slips

    async def run_sgp_with_retry(self):
        class_map = {
            ""
        }



    async def runner(self):
        async with CurlAsyncSession(impersonate="chrome") as session:
            for filters in self.configs:

                logger.info(f"-> Running {filters.get('unique_name')} [{' | '.join(filters.get('stat_types'))}]")

                filter_league = filters.get("league_name")
                stat_types = filters.get("stat_types")

                unique_name = filters.get("unique_name")

                bettorodds_data = self.bettorodds_redis_instance.get_data(key_name="bettorodds_odds") or {}

                filtered_data = bettorodds_data.get(filter_league)

                if not filtered_data:
                    continue

                raw_previous_data = self.previously_stored_redis_instance.get_all_key_values()

                previous_data = set(
                    previous.get("game_key")
                    for previous in raw_previous_data
                )

                slips = self.create_slips(filtered_bettorodds_data=filtered_data, stat_types=stat_types, redis_keys=previous_data,
                                          unique_name=unique_name, league=filter_league)
                print(f"The length of slips: {len(slips)}")
                if not slips:
                    continue

                import json
                with open("slips2.json", "w") as f:
                    json.dump(slips, f, indent=2)




    # async def runner(self):
    #     async with CurlAsyncSession(impersonate="chrome") as session:
    #         stat_types = ["run line", "player hits allowed"]
    #         league_name = "MLB"
    #
    #         pair_list = []
    #         redis_keys = ["2026_08_23 20:15:00Z__arizona_diamondbacks_vs_cincinnati_reds__run_line____ari-1.5_cin+1.5"]
    #         import random
    #
    #         for league, game_information in self.bettorodds_data.items():
    #             if league != league_name:
    #                 continue
    #
    #             for game_name, game_data in game_information.items():
    #                 matched = {}
    #
    #                 # Shuffle the items in game to make sure we get a random pair each time.
    #                 items = list(game_data.items())
    #                 random.shuffle(items)
    #
    #                 for game_id, game in items:
    #                     if game_id in redis_keys:
    #                         continue
    #
    #                     stat = game.get("stat", '').lower()
    #                     if stat in stat_types and stat not in matched:
    #                         matched[stat] = (game_id, game_name)
    #
    #                 if len(matched) == len(stat_types):
    #                     pair_list.append(list(matched.values()))
    #
    #
    #
    #
    #
    #         slips = []
    #
    #         for pairs in pair_list:
    #             pair_data = []
    #             for pair in pairs:
    #                 pair_id = pair[0]
    #                 game_name = pair[1]
    #
    #                 found_item = self.bettorodds_data[league_name][game_name][pair_id]
    #                 pair_data.append(found_item)
    #
    #

if __name__ == "__main__":
    async def main():
        autosgp = await AutoSGP.create()
        await autosgp.runner()


    asyncio.run(main())