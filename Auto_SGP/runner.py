import asyncio
import statistics
from collections import defaultdict
from datetime import datetime, timezone
import importlib
import traceback
import random
from itertools import batched
from Database.base_db import sync_engine
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from Auto_SGP.discord_sender import DiscordSGP
from Auto_SGP.ev_calc_helper import get_sgp_data, parlay_odds
from Auto_SGP.link_generator import Link
from Database.AutoSGP.sgp_db import SGPHistory, SGPLeg, SGPBook, SGPExtraInfo, AutoSGPConfigs
from Settings.book_configurations import BookConfiguration
from Utils.request_caller import APICaller
from curl_cffi import AsyncSession as CurlAsyncSession
from Redis.redis_manager import RedisAsyncManager, RedisSyncManager
from Utils.helpers import is_production
import re
import logging


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class AutoSGP(APICaller):
    SLIP_LENGTH = 50
    PRIORITY_BOOKS = {"prop builder*"}

    def __init__(self, endpoint_redis: RedisAsyncManager, previous_redis_instance: RedisAsyncManager,
                 previously_sent_discord_redis: RedisAsyncManager, redis_book_mapped_ids_instance: RedisAsyncManager,
                 redis_book_auth_instance: RedisAsyncManager, bettorodds_redis_instance: RedisSyncManager, previous_leg_uses: RedisSyncManager,
                 discord_sgp: DiscordSGP, engine: Engine):
        super().__init__()
        self.endpoint_redis = endpoint_redis
        self.previously_stored_redis_instance = previous_redis_instance
        self.previous_leg_uses = previous_leg_uses
        self.previously_sent_discord_redis = previously_sent_discord_redis
        self.redis_book_mapped_ids_instance = redis_book_mapped_ids_instance
        self.redis_book_auth_instance = redis_book_auth_instance
        self.bettorodds_redis_instance = bettorodds_redis_instance
        self.discord_sgp = discord_sgp
        self.database_session =  sessionmaker(bind=engine)


    @classmethod
    async def create(cls):
        """Factory method to create an instance of AutoSGP and set up configurations"""
        production_environment = is_production()

        endpoint_redis = RedisAsyncManager(database=3)
        redis_previously_stored_instance = RedisAsyncManager(database=4)
        previously_sent_discord_redis = RedisAsyncManager(database=5)
        previous_leg_use = RedisSyncManager(database=7)
        redis_book_mapped_ids_instance = RedisAsyncManager(database=2)
        redis_book_auth_instance = RedisAsyncManager(database=1)
        bettorodds_redis_instance = RedisSyncManager(database=6)
        discord_sgp = DiscordSGP(production=production_environment)


        return cls(endpoint_redis=endpoint_redis,
                   previous_redis_instance=redis_previously_stored_instance,
                   previously_sent_discord_redis=previously_sent_discord_redis,
                   redis_book_auth_instance=redis_book_auth_instance,
                   redis_book_mapped_ids_instance=redis_book_mapped_ids_instance,
                   bettorodds_redis_instance=bettorodds_redis_instance,
                   discord_sgp=discord_sgp, engine=sync_engine(),
                   previous_leg_uses=previous_leg_use
                   )

    async def run_sgp_with_retry(self, book_name, book_cls, session, retry_times:int = 3) -> tuple:
        """Run the SGP classes with retries"""
        for attempt in range(retry_times):
            try:
                odds = await book_cls.run_book(session=session)

                if odds:
                    return book_name, odds

            except Exception as e:
                if attempt == retry_times - 1:
                    logger.warning(f"Failed after retries: {e} [{book_name}]")
                    traceback.print_exc()

        return book_name, None

    def _get_book_information(self, book_name: str) -> tuple:
        """Get book information (Ex. Name, Impersonate, Urls, etc)"""
        book_config = BookConfiguration.get_book_info(
            book_type="sgp",
            remove_non_active=True,
            key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path", "curl_impersonation": "impersonate", "alternate_name": "alternate_name"}
        )

        book = next((
            book
            for book in book_config
            if book and book.get("book_key").lower() == book_name.lower()
        ), None)

        if not book:
            return None, None

        module = importlib.import_module(book.get("class_path"))
        my_class = getattr(module, book.get("class_name"))
        return my_class, book.get("impersonate")

    async def run_with_semaphore(self, sem: asyncio.Semaphore, book_name: str, book_cls, impersonate: str) -> tuple:
        """Run the book with semaphore limitations"""
        async with sem:
            async with CurlAsyncSession(impersonate=impersonate) as session:
                return await self.run_sgp_with_retry(
                    book_cls=book_cls,
                    book_name=book_name,
                    session=session,
                )

    async def get_sgp_odds(self, slips_list: list) -> list:
        """Get the SGP odds for all the slips"""
        api_semaphore = asyncio.Semaphore(20)
        ws_semaphore = asyncio.Semaphore(3)

        links = Link()

        async def fetch_slip(slip: dict):
            tasks = []
            for book_name, book_data in slip.get("payload", {}).items():
                class_name, impersonate = self._get_book_information(book_name)

                if not class_name:
                    logger.warning(f"Book not found: {book_name}")
                    continue

                if not impersonate:
                    impersonate = "chrome"

                class_instance = class_name(
                    sgp_data={"book_name": book_name, **book_data},
                    # mapped_ids_redis_instance=self.redis_book_mapped_ids_instance,
                    # auth_redis_instance=self.redis_book_auth_instance,
                )

                tasks.append(self.run_with_semaphore(
                    sem=ws_semaphore if book_name in ["fanatics", "hardrock"] else api_semaphore,
                    book_name=book_name,
                    book_cls=class_instance,
                    impersonate=impersonate
                ))

            task_results = await asyncio.gather(*tasks)

            valid_odds = {
                book_name: odds.get("american_odds")
                for book_name, odds in task_results
                if isinstance(odds, dict) and odds.get("american_odds") is not None
            }

            if len(valid_odds) <= 1:
                return None

            median_data = self._check_median(valid_odds)

            if not median_data or len(median_data.get("median_met_books", {})) <= 1:
                return None

            result = get_sgp_data(
                normal_books=slip.get("individual_odds", {}),
                sgp_results=median_data.get("median_met_books", {}),
                fair_odds=slip.get("fair_value", [])
            )

            filtered_sgp_links = {
                book_name: slip.get("payload", {}).get(book_name, {}).get("links", [])
                for book_name, odds in median_data.get("median_met_books", {}).items()
            }

            sgp_links = links.link_creator(filtered_sgp_links)

            weight_sgp_odds = dict(sorted(result.get("weighted_book_data", {}).items(), key=lambda x: x[1]['ev'], reverse=True))

            return {
                **slip,
                **median_data,
                "sgp_odds": valid_odds,
                "weighted_sgp_odds": weight_sgp_odds,
                "non_correlated_price": parlay_odds(*slip.get("fair_value")),
                "weighted_fair_value": result.get("weighted_fair_value"),
                "sgp_links": sgp_links,
                "time_fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            }

        results = await asyncio.gather(
            *(fetch_slip(slip) for slip in slips_list),
        )


        return [result for result in results if result]

    def _check_median(self, sgp_odds: dict, lower_ratio: float = 0.60) -> dict:
        """
        Check the median of the SGP odds. Creates 2 dicts with medians met and non met.
        :param lower_ratio: Lower ratio threshold
        :param sgp_odds: SGP odds dictionary
        :return: Returns a dict with medians met and non met.
        """
        all_odds = [
            odds
            for odds in sgp_odds.values()
            if isinstance(odds, (int, float))
        ]

        median_value = statistics.median(all_odds)
        lower_bound = median_value * lower_ratio

        median_met = {}
        non_met_median = {}

        for book_name, odds in sgp_odds.items():
            if odds >= lower_bound:
                median_met[book_name] = odds
            else:
                non_met_median[book_name] = odds

        return {
            "median_met_books": median_met,
            "median_non_met_books": non_met_median,
        }

    def create_slips(self, filtered_bettorodds_data: dict, previous_leg_keys: set, previous_leg_uses: dict, unique_name: str,
                     league: str, filter_dict: dict) -> list:
        """
        Creates slips based on the filters
        :param filtered_bettorodds_data: Bettorodds data filtered for the specific league.
        :param previous_leg_keys: Any previous redis keys.
        :param previous_leg_uses: Stored use counts per leg key from previous runs.
        :param unique_name: Unique name for the filter.
        :param league: The league
        :param filter_dict: The filtered dictionary.
        """
        slips = []

        stat_types = [db_filter.lower() for db_filter in filter_dict.get("stat_types", [])]

        max_uses = filter_dict.get("max_uses", 1)
        leg_uses = {}

        for game_name, game_data in filtered_bettorodds_data.items():
            buckets = {stat: [] for stat in stat_types}

            for game in game_data:
                if len(game.get("book_feed")) <= 1:
                    continue

                leg_key = f"{game.get('id')}__{unique_name}"

                if leg_key in previous_leg_keys:
                    continue

                stat = game.get("stat", '').lower()

                if stat in buckets:
                    buckets[stat].append({"event": game_name, "league": league, **game})

                    # Extract previous run so the cap carries across runs. Date is needed for the TTL.
                    leg_uses.setdefault(leg_key, {
                        "count": previous_leg_uses.get(leg_key, 0),
                        "date": game.get("date"),
                        "leg_id": leg_key,
                    })

            seen_keys = set()

            priority_buckets = {
                stat: [leg for leg in bucket_legs if AutoSGP.PRIORITY_BOOKS & set(leg["book_feed"])]
                for stat, bucket_legs in buckets.items()
            }

            # Priority books first, then everything. leg_uses carries over so priority legs aren't reused.
            for active_buckets in (priority_buckets, buckets):
                if not all(active_buckets.values()):
                    continue

                # How many times to re-loop. This allows for stat types to be used again but only the max of max_uses.
                for _ in range(max_uses):
                    # One shuffled slot per stat_type. Returns copies so duplicate stats don't pair with themselves.
                    slots = [random.sample(active_buckets[stat], len(active_buckets[stat])) for stat in stat_types]
                    use_multiple_teams = bool(random.getrandbits(1))

                    for combo in zip(*slots):
                        # Ensure same player + stat isn't used. Ex. (Lebron James Over 5.5 Rebounds + Lebron James Under 5.5 Rebounds)
                        if len(set(leg["unique_stat"] for leg in combo)) != len(combo):
                            continue

                        # Ensure 2 teams.
                        if use_multiple_teams and (len({leg["team"] for leg in combo}) < 2 or any(leg["team"] is None for leg in combo)):
                            continue

                        common_books = set.intersection(*(set(leg["book_feed"]) for leg in combo))
                        if len(common_books) <= 1:
                            continue

                        payload_bucket = {book: {"links": [], "lines": {}, "event_data": []} for book in common_books}
                        individual_odds = {book: [] for book in common_books}
                        legs = []
                        fair_value = []

                        game_key = f"{'__'.join(sorted(str(leg['id']) for leg in combo))}___{unique_name}"

                        if game_key in seen_keys or any(leg_uses[f"{leg['id']}__{unique_name}"]["count"] >= max_uses for leg in combo):
                            continue

                        seen_keys.add(game_key)

                        for leg in combo:
                            leg_uses[f"{leg['id']}__{unique_name}"]["count"] += 1

                        for index, slip in enumerate(combo, start=1):
                            legs.append({
                                "leg_number": index,
                                "market_type": slip.get("stat"),
                                "line": slip.get("line"),
                                "direction": slip.get("side"),
                                "team": slip.get("team"),
                                "player_name": slip.get("player"),
                                "normalized": slip.get("normalized_name"),
                                "unique_stat": slip.get("unique_stat"),
                                "id": slip["id"],
                                "event": slip.get("event"),
                                "date": slip.get("date"),
                                "league": slip.get("league"),
                                "nvig": slip.get("nvig"),
                                "odds": {
                                    book_name: book_data.get("american_odds")
                                    for book_name, book_data in slip.get("book_feed", {}).items()
                                }
                            })

                            fair_value.append(slip.get("nvig"))

                            for book in common_books:
                                data = slip["book_feed"][book]
                                payload_bucket[book]["links"].append(data["bet_link"])
                                payload_bucket[book]["lines"].update({data["bet_link"]: slip.get("line")})
                                payload_bucket[book]["event_data"].append({
                                    "market_name": slip.get("stat"),
                                    "date": combo[0]["date"],
                                    "event_name": combo[0]["event"],
                                    "line": slip.get("line"),
                                    "player": slip.get("player"),
                                    "side": slip.get("side"),
                                    # "selection_name": f"{slip.get('player', '')} {slip.get('side', '')} {slip.get('line', '')}".strip(),
                                    "prop_key": slip.get("prop_key"),
                                    "event_key": slip.get("event_key"),
                                })
                                individual_odds[book].append(data["american_odds"])

                        slips.append({
                            "game_key": game_key,
                            "event": combo[0]["event"],
                            "date": combo[0]["date"],
                            "league": combo[0]["league"],
                            "discord_sent": False,
                            "legs": legs,
                            "unique_filter_name": unique_name,
                            "individual_odds": individual_odds,
                            "fair_value": fair_value,
                            "payload": payload_bucket,
                        })

        if leg_uses:
            self.previous_leg_uses.bulk_insert_individual(
                data_to_store=leg_uses
            )

        return slips

    # def create_slips(self, filtered_bettorodds_data: dict, previous_leg_keys: set, previous_leg_uses: dict, unique_name: str,
    #                  league: str, filter_dict: dict) -> list:
    #     """
    #     Creates slips based on the filters
    #     :param filtered_bettorodds_data: Bettorodds data filtered for the specific league.
    #     :param previous_leg_keys: Any previous redis keys.
    #     :param previous_leg_uses: Stored use counts per leg key from previous runs.
    #     :param unique_name: Unique name for the filter.
    #     :param league: The league
    #     :param filter_dict: The filtered dictionary.
    #     """
    #     slips = []
    #
    #     stat_types = [db_filter.lower() for db_filter in filter_dict.get("stat_types", [])]
    #     use_multiple_teams = filter_dict.get("multiple_teams")
    #     max_uses = filter_dict.get("max_uses", 1)
    #     leg_uses = {}
    #
    #     for game_name, game_data in filtered_bettorodds_data.items():
    #         buckets = {stat: [] for stat in stat_types}
    #
    #         for game in game_data:
    #             if len(game.get("book_feed")) <= 1:
    #                 continue
    #
    #             leg_key = f"{game.get('id')}__{unique_name}"
    #
    #             if leg_key in previous_leg_keys:
    #                 continue
    #
    #             stat = game.get("stat", '').lower()
    #
    #             if stat in buckets:
    #                 buckets[stat].append({"event": game_name, "league": league, **game})
    #
    #                 # Extract previous run so the cap carries across runs. Date is needed for the TTL.
    #                 leg_uses.setdefault(leg_key, {
    #                     "count": previous_leg_uses.get(leg_key, 0),
    #                     "date": game.get("date"),
    #                     "leg_id": leg_key,
    #                 })
    #
    #         seen_keys = set()
    #
    #         # How many times to re-loop. This allows for stat types to be used again but only the max of max_uses.
    #         for _ in range(max_uses):
    #             # One shuffled slot per stat_type. Returns copies so duplicate stats don't pair with themselves.
    #             slots = [random.sample(buckets[stat], len(buckets[stat])) for stat in stat_types]
    #
    #             for combo in zip(*slots):
    #                 # Ensure same player + stat isn't used. Ex. (Lebron James Over 5.5 Rebounds + Lebron James Under 5.5 Rebounds)
    #                 if len(set(leg["unique_stat"] for leg in combo)) != len(combo):
    #                     continue
    #
    #                 # Ensure 2 teams.
    #                 if use_multiple_teams and (len({leg["team"] for leg in combo}) < 2 or any(leg["team"] is None for leg in combo)):
    #                     continue
    #
    #                 common_books = set.intersection(*(set(leg["book_feed"]) for leg in combo))
    #
    #                 if len(common_books) <= 1:
    #                     continue
    #
    #                 payload_bucket = {book: {"links": [], "lines": {}, "event_data": []} for book in common_books}
    #                 individual_odds = {book: [] for book in common_books}
    #                 legs = []
    #                 fair_value = []
    #
    #                 game_key = f"{'__'.join(sorted(str(leg['id']) for leg in combo))}___{unique_name}"
    #
    #                 if game_key in seen_keys or any(leg_uses[f"{leg['id']}__{unique_name}"]["count"] >= max_uses for leg in combo):
    #                     continue
    #
    #                 seen_keys.add(game_key)
    #
    #                 for leg in combo:
    #                     leg_uses[f"{leg['id']}__{unique_name}"]["count"] += 1
    #
    #                 for index, slip in enumerate(combo, start=1):
    #                     legs.append({
    #                         "leg_number": index,
    #                         "market_type": slip.get("stat"),
    #                         "line": slip.get("line"),
    #                         "direction": slip.get("side"),
    #                         "team": slip.get("team"),
    #                         "player_name": slip.get("player"),
    #                         "normalized": slip.get("normalized_name"),
    #                         "unique_stat": slip.get("unique_stat"),
    #                         "id": slip["id"],
    #                         "event": slip.get("event"),
    #                         "date": slip.get("date"),
    #                         "league": slip.get("league"),
    #                         "nvig": slip.get("nvig"),
    #                         "odds": {
    #                             book_name: book_data.get("american_odds")
    #                             for book_name, book_data in slip.get("book_feed", {}).items()
    #                         }
    #                     })
    #
    #                     fair_value.append(slip.get("nvig"))
    #
    #                     for book in common_books:
    #                         data = slip["book_feed"][book]
    #                         payload_bucket[book]["links"].append(data["bet_link"])
    #                         payload_bucket[book]["lines"].update({data["bet_link"]: slip.get("line")})
    #                         payload_bucket[book]["event_data"].append({
    #                             "market_name": slip.get("stat"),
    #                             "date": combo[0]["date"],
    #                             "event_name": combo[0]["event"],
    #                             "line": slip.get("line"),
    #                             "player": slip.get("player"),
    #                             "side": slip.get("side"),
    #                             # "selection_name": f"{slip.get('player', '')} {slip.get('side', '')} {slip.get('line', '')}".strip(),
    #                             "prop_key": slip.get("prop_key"),
    #                             "event_key": slip.get("event_key"),
    #                         })
    #                         individual_odds[book].append(data["american_odds"])
    #
    #                 slips.append({
    #                     "game_key": game_key,
    #                     "event": combo[0]["event"],
    #                     "date": combo[0]["date"],
    #                     "league": combo[0]["league"],
    #                     "discord_sent": False,
    #                     "legs": legs,
    #                     "unique_filter_name": unique_name,
    #                     "individual_odds": individual_odds,
    #                     "fair_value": fair_value,
    #                     "payload": payload_bucket,
    #                 })
    #
    #     if leg_uses:
    #         self.previous_leg_uses.bulk_insert_individual(
    #             data_to_store=leg_uses
    #
    #         )
    #
    #     return slips

    def _store_history(self, endpoint_data: dict):
        """Stores the SGP results to the database for history tracking"""
        game_keys = []
        legs = []
        books = []
        extra_info = []

        with self.database_session.begin() as session:
            for endpoint in endpoint_data.values():
                game_key = endpoint["game_key"]
                timestamp = datetime.fromisoformat(endpoint["time_fetched"].replace("Z", "+00:00"))
                game_keys.append({"game_key": game_key})

                extra_info.append({
                    "game_key": game_key,
                    "non_correlated_price": endpoint["non_correlated_price"],
                    "weighted_fair_value": endpoint["weighted_fair_value"],
                    "timestamp": timestamp
                })

                for book_name, sgp_odds in endpoint["sgp_odds"].items():
                    books.append({
                        "game_key": game_key,
                        "book_name": book_name,
                        "sgp_odd": sgp_odds,
                        "median_met": True if book_name in endpoint.get("median_met_books", {}) else False,
                        "ev": endpoint.get("weighted_sgp_odds", {}).get(book_name, {}).get("ev", None),
                        "timestamp": timestamp
                    })

                for l in endpoint["legs"]:
                    line = l["line"]

                    # Extract line for spread cases.
                    if not line:
                        pattern_match = re.search(r"\d+(?:\.\d+)?", l["direction"])
                        line = pattern_match.group() if pattern_match else None

                    legs.append({
                        "game_key": game_key,
                        "event_league": l["league"],
                        "event_date": l["date"],
                        "event_name": l["event"],
                        "leg_number": l["leg_number"],
                        "normalized_name": l["normalized"],
                        "market_type": l["market_type"],
                        "individual_odds": l["odds"],
                        "line": line,
                        "team": l["team"],
                        "player_name": l["player_name"],
                        "nvig": l["nvig"],
                        "timestamp": timestamp
                    })

            if game_keys:
                smt_game_keys = insert(SGPHistory).on_conflict_do_nothing(index_elements=["game_key"])
                session.execute(smt_game_keys, game_keys)

            if legs:
                smt_leg = insert(SGPLeg).on_conflict_do_nothing(constraint="leg_unique_time_name_game_key")
                session.execute(smt_leg, legs)

            if books:
                smt_books = insert(SGPBook).on_conflict_do_nothing(constraint="book_unique_time_book_name_game_key")
                session.execute(smt_books, books)

            if extra_info:
                smt_extra = insert(SGPExtraInfo).on_conflict_do_nothing(constraint="extra_unique_time_game_key")
                session.execute(smt_extra, extra_info)

    def _add_random_filters(self, auto_filters: list):
        database_stat_types = defaultdict(set)
        for auto_filter in auto_filters:
            database_stat_types[auto_filter.get("league_name")].update(auto_filter.get("stat_types"))

        bettorodds_data = self.bettorodds_redis_instance.get_data(key_name="bettorodds_odds") or {}
        bettorodds_stat_types = defaultdict(set)

        for league, league_data in bettorodds_data.items():
            for props in league_data.values():
                for prop in props:
                    if not isinstance(prop, dict):
                        continue

                    bettorodds_stat_types[league].add(prop.get("stat"))

        new_stat_types = defaultdict(set)

        for league, stat_types in bettorodds_stat_types.items():
            found = database_stat_types.get(league)
            if found:
                result = stat_types.symmetric_difference(found)
                new_stat_types[league].update(result)
            else:
                new_stat_types[league].update(stat_types)

        new_stat_types = dict(new_stat_types)

        for league, stat in new_stat_types.items():
            random_leg_amount = random.randint(2, 6)
            combos = [pair for pair in batched(stat, random_leg_amount) if len(pair) == random_leg_amount]

            for combo in combos:
                unique_name = f"{league}_{'_'.join(combo).replace(' ', '_')}".lower()

                auto_filters.append({
                    "unique_name": unique_name,
                    "league_name": league,
                    "stat_types": [*combo],
                    "multiple_teams": bool(random.getrandbits(1)), # Random True or False
                    "discord_min_ev": 15.0,
                    "max_uses": random.randint(1, 3),
                    "is_active": True,
                })

        return auto_filters



    async def runner(self):
        """Primary function to run everything"""
        logging.getLogger("sqlalchemy.engine").propagate = False

        with self.database_session() as session:
            auto_filters = AutoSGPConfigs.get_active_configs(session)

        if not auto_filters:
            raise Exception("No active AutoSGP configs found.")

        auto_filters = self._add_random_filters(auto_filters)

        for filters in auto_filters[0:1]:
            logger.info(f"-> Running {filters.get('unique_name')} [{' | '.join(filters.get('stat_types'))}]")

            filter_league = filters.get("league_name")
            unique_name = filters.get("unique_name")

            bettorodds_data = self.bettorodds_redis_instance.get_data(key_name="bettorodds_odds") or {}

            filtered_data = bettorodds_data.get(filter_league)

            if not filtered_data:
                logger.warning(f"No Filter Data found for {filter_league}")
                continue

            raw_previous_leg_keys = await self.previously_stored_redis_instance.get_all_key_values()
            raw_previous_game_keys = await self.previously_sent_discord_redis.get_all_key_values()
            raw_previous_leg_uses = self.previous_leg_uses.get_all_key_values()

            previous_leg_keys = set(
                previous.get("leg_id")
                for previous in raw_previous_leg_keys
            )

            previous_game_keys = set(
                previous.get("game_key")
                for previous in raw_previous_game_keys
            )

            previous_leg_uses = {
                previous.get("leg_id"): previous.get("count", 0)
                for previous in raw_previous_leg_uses
            }

            slips = self.create_slips(filtered_bettorodds_data=filtered_data, previous_leg_keys=previous_leg_keys,
                                      previous_leg_uses=previous_leg_uses, unique_name=unique_name, league=filter_league,
                                      filter_dict=filters)

            import json
            with open(f"slips.json", "w") as f:
                json.dump(slips, f, indent=2)

            # if not slips:
            #     logger.warning(f"No slips created for {unique_name}")
            #     continue
            #
            # batch_legs = {}
            # batch_discord = {}
            # endpoint = {}
            #
            # for i in range(0, len(slips[0:AutoSGP.SLIP_LENGTH]), 10):
            #     batch = slips[i:i + 10]
            #     print(f"  → Batch {i // 10 + 1}: {len(batch)} items")
            #     results = await self.get_sgp_odds(slips_list=batch)
            #
            #     for slip in results:
            #         ev_count = sum(
            #             1
            #             for book_data in slip.get("weighted_sgp_odds").values()
            #             if book_data.get("ev", 0) >= filters.get("discord_min_ev")
            #         )
            #
            #         game_key = slip.get("game_key")
            #
            #         if all([
            #             ev_count == 1,
            #             len(slip.get("median_met_books", 0)) >= 3,
            #             game_key,
            #             game_key not in previous_game_keys
            #         ]):
            #             slip["discord_sent"] = True
            #             self.discord_sgp.send_alert(slip=slip)
            #
            #         game_dates = [leg["date"] for leg in slip["legs"] if leg.get("date")]
            #         soonest_date = min(game_dates, key=datetime.fromisoformat) if game_dates else slip.get("date")
            #
            #         if slip["discord_sent"]:
            #             batch_discord.update({
            #                 game_key: {
            #                     "date": soonest_date,
            #                     "game_key": game_key,
            #                 }
            #             })
            #
            #         batch_legs.update({
            #             f"{leg['id']}__{unique_name}": {
            #                 "date": leg["date"],
            #                 "leg_id": f"{leg['id']}__{unique_name}",
            #             }
            #             for leg in slip["legs"]
            #         })
            #
            #         slip.pop("payload")
            #
            #         endpoint.update({
            #             game_key: {
            #                 **slip,
            #                 "date": soonest_date
            #             }
            #         })
            #
            # if batch_legs:
            #     await self.previously_stored_redis_instance.bulk_insert_individual(
            #         data_to_store=batch_legs
            #
            #     )
            #
            # if batch_discord:
            #     await self.previously_sent_discord_redis.bulk_insert_individual(
            #         data_to_store=batch_discord
            #
            #     )
            #
            # if endpoint:
            #     await self.endpoint_redis.bulk_insert_individual(
            #         data_to_store=endpoint
            #
            #     )
            #
            #     self._store_history(endpoint_data=endpoint)


if __name__ == "__main__":
    async def main():
        autosgp = await AutoSGP.create()
        await autosgp.runner()

    asyncio.run(main())