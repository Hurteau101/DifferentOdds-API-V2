import asyncio
import statistics
from datetime import datetime, timezone
import itertools
import os
import aiohttp
from dotenv import load_dotenv
import json
import copy

from Auto_SGP.Helper.ev_calc_helper import get_sgp_data, parlay_odds
from Auto_SGP.Mappers.espn import ESPN
from Auto_SGP.discord_sender import DiscordSGP
from Auto_SGP.link_generator import Link
from Auto_SGP.settings import BOOKS, URLS
from Auto_SGP.slips import SlipMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import APICaller, SportbookRequestType




import traceback

class AutoSGP(APICaller):
    load_dotenv()
    def __init__(self, endpoint_redis: RedisAsyncManager, configs: dict, previous_redis_instance: RedisAsyncManager,
                 previously_sent_discord_redis: RedisAsyncManager, mapped_ids_redis_instance: RedisAsyncManager,
                 auth_redis_instance: RedisAsyncManager, discord_sgp: DiscordSGP):
        super().__init__(request_type=SportbookRequestType.ASYNC)
        self.endpoint_redis = endpoint_redis
        self.configs = configs
        self.previously_stored_redis_instance = previous_redis_instance
        self.previously_sent_discord_redis = previously_sent_discord_redis
        self.discord_sgp = discord_sgp
        self.mapped_ids_redis_instance = mapped_ids_redis_instance
        self.auth_redis_instance = auth_redis_instance

    @classmethod
    async def create(cls):
        """Factory method to create an instance of AutoSGP and set up configurations"""
        config_instanace = RedisAsyncManager(database=8)
        configs = await config_instanace.get_data("configs")
        if not configs:
            raise RuntimeError("Configs not were not loaded")

        environment_type = os.getenv("ENVIRONMENT")
        if not environment_type:
            raise RuntimeError("Environment not set")

        endpoint_redis = RedisAsyncManager(database=10)
        redis_previously_stored_instance = RedisAsyncManager(database=9)
        previously_sent_discord_redis = RedisAsyncManager(database=12)
        redis_mapped_ids_instance = RedisAsyncManager(database=2)
        redis_auth_instance = RedisAsyncManager(database=5)

        production = environment_type.lower() == "production"
        discord_sgp = DiscordSGP(production=production)


        return cls(endpoint_redis=endpoint_redis, configs=configs,
                   previous_redis_instance=redis_previously_stored_instance,
                   previously_sent_discord_redis=previously_sent_discord_redis,
                   discord_sgp=discord_sgp, auth_redis_instance=redis_auth_instance,
                   mapped_ids_redis_instance=redis_mapped_ids_instance)


    async def _load_sportsbook_data(self, session: aiohttp.ClientSession, limit: str | int = "all",
                                    store_json: bool = False, used_stored_json: bool = False):
        """Loads BettorOdds Sportsbook data"""
        if store_json and used_stored_json:
            raise ValueError("Cannot store and use stored JSON")

        if used_stored_json:
            with open("bettorodds_data.json", "r") as f:
                return json.load(f)

        api_key = os.getenv("INTERNAL_BETTORODDS_API_KEY")
        if not api_key:
            create_sentry_message(
                tag_key="bettorodds",
                tag_value="api_key_failure",
                message="No API Key found",
                level="error"
            )
            return

        sports_data = await self.api_caller(
            book_name="AutoSGP",
            session=session,
            url=URLS.get("bettorodds_url"),
            method="GET",
            headers={
                "auth_token": api_key,
                "limit": limit
            }

        )

        if not sports_data:
            return

        if store_json:
            with open("bettorodds_data.json", "w") as f:
                json.dump(sports_data, f, indent=2)

            print("BetterOdds Data Stored As 'bettorodds_data.json'")

        return sports_data

    def _normalize_book_odds(self, markets: dict, valid_sgp_books: set) -> dict:
        """
        Normalize the book odds from the markets data. Returns a dictionary with book name and over/under odds.
        """
        odds = {}

        for book_name, sides in markets.get("book_feed", {}).items():
            if book_name.lower() not in valid_sgp_books:
                continue

            for side, data in sides.items():
                am_odds = data.get("am_odds")
                if isinstance(am_odds, (int, float)):
                    odds.setdefault(book_name.lower(), {})[side.lower()] = am_odds

        return odds


    def _get_book_information(self, book_feed: dict, valid_sgp_books: set, markets: dict):
        """Gather the over and under information from the book feed."""
        books = {"Over": {}, "Under": {}}

        line = markets.get("Line", None)

        for book_name, sides in book_feed.items():
            if book_name.lower() not in valid_sgp_books:
                continue

            mapped_book_name = BOOKS.get(book_name.lower(), book_name.lower()).get("mapped_name", book_name.lower())

            for side_name, side_information in sides.items():
                selection_name = markets.get("Stat", None)
                if markets.get("Player"):
                    selection_name = f"{markets.get('Player')} {side_name} {line}"

                if side_information.get("betlink") or side_information.get("internal_betlink"):
                    betlink = side_information.get("betlink") or side_information.get("internal_betlink")
                    books[side_name][mapped_book_name] = {
                        "betlink": betlink,
                        "american_odds": side_information.get("am_odds"),
                        "line": {betlink: float(line)} if line else None,
                        "event_data": {
                            "market_name": markets.get("Prop", None),
                            "selection_name": selection_name
                        }
                    }

        return books

    async def _filter_data(self, bettorodds_data: dict, filter_selection: dict, player_mapping: dict,
                           previous_data: dict, configs: dict) -> dict:

        valid_sgp_books = set(
            book_name
            for book_name, book_data in BOOKS.items()
            if book_data.get("active")
        )

        results = {}

        for game_key, markets in bettorodds_data.items():
            redis_key = f"{filter_selection.get('unique_name')}-{game_key}"
            if redis_key in previous_data.keys():
                continue

            if (
                markets.get("League", "").lower() == filter_selection.get("league", "").lower()
                and markets.get("Prop", "").lower() in filter_selection.get("stat_types", [])
                and not markets.get("one_way")
            ):
                # Ensure at least one book has a main line. If not, skip this market.
                any_main = any(
                    book_data.get("is_main")
                    for book_name, sides in markets.get("book_feed", {}).items()
                    if book_name.lower() in valid_sgp_books
                    for book_data in sides.values()
                )


                if not any_main:
                    continue

                current_odds = self._normalize_book_odds(markets, valid_sgp_books)

                books = self._get_book_information(markets.get("book_feed", {}), valid_sgp_books, markets)

                num_unique_books = len({book for side in books.values() for book in side})

                if num_unique_books >= filter_selection.get("number_of_unique_books", 0):
                    unique_stats = ["team total"]

                    results[game_key] = {
                        "game_key": redis_key,
                        "stat_name": markets.get("Prop").replace("Player", "").strip(),
                        "market_type": "player" if "Player" in markets.get("Prop") else "team",
                        "league": markets.get("League"),
                        "bet_info": markets.get("Prop"),
                        "stat": markets.get("Unique Stat"),
                        "actual_stat": markets.get("Stat"),
                        "date": markets.get("Date"),
                        "player": markets.get("Player"),
                        "team": player_mapping.get(markets.get("Player"), "") if markets.get(
                            "Prop").lower() not in unique_stats else markets.get("Player"),
                        "event": markets.get("Match"),
                        "current_odds": current_odds,
                        "nvig_map": markets.get("nvig_map"),
                        "books": {key: value for key, value in books.items() if value},
                        "configs": configs,
                    }

        await self.previously_stored_redis_instance.bulk_insert_individual(
            data_to_store=results,
            pipeline=self.previously_stored_redis_instance.redis_client.pipeline()
        )

        return results


    def index_previous_data(self, previous_data: list):
        return {
            data.get("game_key"): data
            for data in previous_data
        }


    def _create_payload(self, odds_data: list, direction_tuple: tuple[str, str]) -> list:
        """
        Create the payload based on the odds data and direction tuple.
        :param odds_data: The odds data.
        :param direction_tuple: The tuple of directions (e.g., ("over", "under")).
        :return: Returns the created payload.
        """
        payload = []

        for data in odds_data:
            leg_books = []
            leg_fair = []
            leg_keys = []
            stat_directions = {}

            # Iterate through each stat type and direction
            for i, direction in enumerate(direction_tuple, start=1):
                direction = direction.title()

                books = data.get(f"stat_type_{i}_books", {})
                if not books:
                    continue

                # Store the "Over" or "Under" books based on the direction
                dir_books = books.get(direction)
                if not dir_books:
                    break

                leg_books.append(dir_books)
                leg_fair.append(data.get(f"stat_type_{i}_nvig_map", {}).get(direction))
                leg_keys.append((data.get(f"game_key_{i}"), direction))
                stat_directions[f"stat_{i}_direction"] = direction

                # Ensure the # of legs matches the number of directions
            if len(leg_books) != len(direction_tuple):
                continue

            # Create a set of common books.
            common_books = set.intersection(*(set(book.keys()) for book in leg_books))
            if len(common_books) < 2:
                continue

            valid_books = []
            normal_books = {}

            # Loop through common books and create a payload
            for book in common_books:
                links = []
                odds = []
                lines = {}
                event_data = []

                for dir_books in leg_books:
                    entry = dir_books.get(book, {})
                    betlink = entry.get("betlink")
                    links.append(betlink)
                    odds.append(entry.get("american_odds"))
                    lines.update(entry.get("line", {}))
                    event_data.append(entry.get("event_data"))

                valid_books.append({
                    "book_name": book.lower(),
                    "links": links,
                    "lines": lines,
                    "event_data": event_data,
                })

                normal_books[book.lower()] = odds

            # Must have 2 matching books
            if len(valid_books) < 2:
                continue

            redis_key = "-".join([f"{game_key}-{direction}" for game_key, direction in leg_keys])

            payload.append({
                **data,
                **stat_directions,
                "payload": valid_books,
                "normal_books": normal_books,
                "fair_value": leg_fair,
                "redis_game_key": redis_key
            })

        return payload

    def _create_direction_combos(self, directions: tuple, selection_odds: list) -> list:
        """
        Create all possible direction combinations based on the provided directions and selection odds.
        :param directions: The tuple of directions (e.g., ("over", "under")).
        :param selection_odds: The selection odds data.
        :return: Returns the created direction combinations in a list.
        """

        if not directions or not selection_odds:
            raise ValueError("Directions and selection_odds cannot be empty.")

        lower_dirs = tuple(d.lower() for d in directions)

        # In case all directions are the same, only create two combinations [all over, all under]
        if len(set(lower_dirs)) == 1:
            results = []
            results.extend(self._create_payload(selection_odds, lower_dirs))

            opposite = tuple("under" if d == "over" else "over" for d in lower_dirs)
            results.extend(self._create_payload(selection_odds, opposite))

            return results


        all_directions = list(itertools.product(["over", "under"], repeat=len(directions)))
        direction_combos = []
        for combo in all_directions:
            payload = self._create_payload(selection_odds, combo)
            direction_combos.extend(payload)

        return direction_combos

    def _generate_links(self, payload: list, sgp_books_with_odds) -> dict:
        """
        Generate links for the given payload.
        :param payload: Payload of data
        :return: Returns a dictionary of generated links.
        """
        filtered_payload = [
            item
            for item in payload
            if item.get("book_name") in sgp_books_with_odds
        ]

        links = Link()
        return links.link_creator(filtered_payload)

    def extract_endpoint_data(self, sgp_data: dict, books: dict, individual_odds_dict: dict, fair_value_odds: dict):
        if not books.get("valid"):
            return {}

        sorted_data_sgp_odds = dict(
            sorted(books.get("filtered_sgp_books", {}).items(), key=lambda x: x[1], reverse=True))

        sgp_data.update({
            "filtered_sgp_odds": sorted_data_sgp_odds,
            "non_met_books": books.get("non_met_books"),
            "filtered_individual_odds": books.get("filtered_individual_books"),
        })

        result = get_sgp_data(
            normal_books=individual_odds_dict,
            sgp_results=sorted_data_sgp_odds,
            fair_odds=fair_value_odds
        )

        weighted_data = result.get("weighted_book_data")
        weighted_fair = result.get("weighted_fair_value")

        return {
            sgp_data.get("redis_key"): {
                **sgp_data,
                "ev_results": {
                    "weighted_book_data": dict(sorted(weighted_data.items(), key=lambda x: x[1]['ev'], reverse=True)),
                    "weighted_fair_value": weighted_fair,
                }
            }
        }

    async def extract_and_send_discord_data(self, sgp_data: dict, books: dict, individual_odds_dict: dict,
                                      fair_value_odds: dict, minimum_ev: float):
        if not books.get("valid"):
            return {}

        sgp_data.update({
            "filtered_sgp_odds": books.get("filtered_sgp_books"),
            "non_met_books": books.get("non_met_books"),
            "filtered_individual_odds": books.get("filtered_individual_books"),
        })

        result = get_sgp_data(
            normal_books=individual_odds_dict,
            sgp_results=books.get("filtered_sgp_books", {}),
            fair_odds=fair_value_odds
        )

        weighted_data = result.get("weighted_book_data")
        non_correlated_price = parlay_odds(*sgp_data.get("fair_value"))

        ev_count = sum(
            1 for book_data in weighted_data.values()
            if book_data.get("ev", 0) >= minimum_ev
        )

        meets_ev_threshold = ev_count == 1

        if not meets_ev_threshold:
            return {}

        filtered_links = {
            book: sgp_data.get("sgp_links", {}).get(book)
            for book, data in weighted_data.items()
            if data.get("ev", -999) >= minimum_ev and book in sgp_data.get("sgp_links", {})
        }

        sgp_data.update({
            "ev_results": weighted_data,
            "weighted_fair_value": result.get("weighted_fair_value"),
            "fair_parlay_price": non_correlated_price,
            "filtered_links": filtered_links,
            "minimum_ev": minimum_ev
        })

        redis_key = sgp_data.get("redis_key")

        already_sent = await self.previously_sent_discord_redis.get_data(redis_key)
        if already_sent:
            return {}

        # print(f"Sending SGP Alert for {sgp_data.get('event')} on {sgp_data.get('date')} with minimum EV of {minimum_ev}%")
        self.discord_sgp.send_alert(sgp_data=sgp_data)

        return {
            redis_key: sgp_data
        }


    async def controller(self, sgp_data: dict, minimum_ev: float) -> dict:
        individual_odds_dict = sgp_data.get("individual_odds_dict", {})
        sgp_odds = sgp_data.get("sgp_odds", {})
        fair_value = sgp_data.get("fair_value", {})

        if not any([individual_odds_dict, sgp_odds, fair_value]):
            return {}

        endpoint_books = self._check_median(sgp_odds=sgp_odds, valid_amount_of_books=2,
                                            individual_odds_dict=individual_odds_dict)

        discord_books = self._check_median(sgp_odds=sgp_odds, individual_odds_dict=individual_odds_dict, valid_amount_of_books=4)

        endpoint_sgp_data = self.extract_endpoint_data(
            sgp_data=copy.deepcopy(sgp_data), books=endpoint_books, individual_odds_dict=individual_odds_dict,
            fair_value_odds=fair_value)

        discord_sgp_data = await self.extract_and_send_discord_data(sgp_data=sgp_data, books=discord_books,
                                                              individual_odds_dict=individual_odds_dict,
                                                              fair_value_odds=fair_value, minimum_ev=minimum_ev)

        return {
            "endpoint": endpoint_sgp_data,
            "discord": discord_sgp_data
        }



    def _check_median(self, sgp_odds: dict, individual_odds_dict: dict, valid_amount_of_books: int = 4, lower_ratio: float = 0.60, ) -> dict:
        """
        Check the median of the SGP odds and filter out books that do not meet the lower ratio threshold.
        :param lower_ratio: Lower ratio threshold
        :param sgp_odds: SGP odds dictionary
        :param individual_odds_dict: Individual odds dictionary
        :param valid_amount_of_books: How many valid books are required
        :return: Returns a dictionary with the filtered books and non-met books.
        """

        all_odds = [
            odds for odds in sgp_odds.values()
            if isinstance(odds, (int, float))
        ]

        if len(all_odds) <= 1:
            return {
                "valid": False,
                "filtered_books": {},
                "non_met_books": []
            }

        median_value = statistics.median(all_odds)
        lower_bound = median_value * lower_ratio

        filtered_books = {}
        non_met_books = []

        for book_name, odds in sgp_odds.items():
            if odds >= lower_bound:
                filtered_books[book_name] = odds
            else:
                non_met_books.append({book_name: odds})

        if len(filtered_books) < valid_amount_of_books:
            return {
                "valid": False,
                "filtered_books": {},
                "non_met_books": []
            }

        filtered_individual = {
            book: individual_odds_dict[book]
            for book in filtered_books.keys()
            if book in individual_odds_dict
        }

        return {
            "valid": True,
            "filtered_sgp_books": filtered_books,
            "filtered_individual_books": filtered_individual,
            "non_met_books": non_met_books
        }


    async def run_sgp_with_retry(self, book_cls, book_name, session, retry_times=3):
        for attempt in range(retry_times):
            try:
                odds = await book_cls.run_book(session=session)

                if odds:
                    return book_name, odds

            except Exception as e:
                if attempt == retry_times - 1:
                    print(f"Failed after retries: {e} [{book_name}]")
                    traceback.print_exc()

        return book_name, None

    # async def get_sgp_odds(self, payload_data: list, session, minimum_ev: float, batch_size: int = 25, retry_times: int = 1):
    #     mapped_names = {
    #         book_data.get("mapped_name"): book_data
    #         for book_data in BOOKS.values()
    #         if book_data.get("active")
    #     }
    #
    #
    #     async def fetch_single(payload_item: dict):
    #         tasks = []
    #
    #         for book in payload_item.get("payload", []):
    #             book_name = book.get("book_name")
    #             book_cls_name = mapped_names.get(book_name, {}).get("class")
    #
    #             if not book_cls_name:
    #                 print("No Class Found for Book:", book_name)
    #                 continue
    #
    #             sgp_data = {
    #                 "book_name": book_name,
    #                 "links": book.get("links"),
    #                 "lines": book.get("lines"),
    #                 "event_data": book.get("event_data"),
    #             }
    #
    #
    #             book_cls = book_cls_name(sgp_data=sgp_data, mapped_ids_redis_instance=self.mapped_ids_redis_instance,
    #                                            auth_redis_instance=self.auth_redis_instance)
    #
    #             tasks.append(
    #                 self.run_sgp_with_retry(book_cls=book_cls, book_name=book_name, retry_times=retry_times, session=session)
    #             )
    #
    #         results = await asyncio.gather(*tasks)
    #
    #         valid_odds = {
    #             book_name: odds_value.get("american_odds")
    #             for book_name, odds_value in results
    #             if isinstance(odds_value, dict)
    #                and odds_value.get("american_odds") is not None
    #         }
    #
    #         print(valid_odds)
    #
    #         # ####### JUST FOR TESTING #########
    #         # invalid_odds = {
    #         #     book_name
    #         #     for book_name, odds_value in results
    #         #     if not odds_value
    #         # }
    #         #
    #         # if invalid_odds:
    #         #     event = payload_item.get("event")
    #         #     stat_type_1_line = payload_item.get("stat_type_1_line")
    #         #     stat_type_2_line = payload_item.get("stat_type_2_line")
    #         #     stat_type_1_direction = payload_item.get("stat_1_direction")
    #         #     stat_type_2_direction = payload_item.get("stat_2_direction")
    #         #     stat_name_1 = payload_item.get("stat_name_1")
    #         #     stat_name_2 = payload_item.get("stat_name_2")
    #         #
    #         #     log_lines = []
    #         #     log_lines.append("-" * 60)
    #         #     log_lines.append(str(invalid_odds))
    #         #     log_lines.append(f"Event: {event}")
    #         #     log_lines.append(f"Stat Type 1: {stat_type_1_line} {stat_type_1_direction} {stat_name_1}")
    #         #     log_lines.append(f"Stat Type 2: {stat_type_2_line} {stat_type_2_direction} {stat_name_2}")
    #         #     log_lines.append("Payload Details:")
    #         #
    #         #     for book_test in invalid_odds:
    #         #         payload_item_test = next(
    #         #             (item for item in payload_item.get("payload", [])
    #         #              if item.get("book_name") == book_test),
    #         #             None
    #         #         )
    #         #
    #         #         log_lines.append(f"- {book_test}: {payload_item_test}")
    #         #
    #         #         mapping_books = {
    #         #             "fanduel": {"map_key": "fanduel_ids"},
    #         #             "caesars": {"map_key": "caesar_mapped_ids"},
    #         #             "betmgm": {"map_key": "betmgm_ids"}
    #         #         }
    #         #
    #         #         if book_test in mapping_books:
    #         #             map_key = mapping_books[book_test]["map_key"]
    #         #
    #         #             mapped_instance = RedisAsyncManager(database=2)
    #         #             has_mapping = await mapped_instance.get_data(map_key)
    #         #
    #         #             if not has_mapping:
    #         #                 log_lines.append(f"  -> No mapping IDS found for: {book_test}")
    #         #
    #         #     print("\n".join(log_lines))
    #
    #         ##############################################
    #
    #         if len(valid_odds) <= 1:
    #             print("Not enough valid odds found: ", valid_odds)
    #             return {}
    #
    #         def include_key(key: str) -> bool:
    #             return (
    #                 (key.startswith("stat_") and key.endswith("_direction")) or
    #                 key.startswith("stat_name_") or
    #                 (key.startswith("stat_type_") and key.endswith("_line")) or
    #                 key.startswith("team_") or
    #                 key.startswith("market_type_")
    #             )
    #
    #         sgp_details = {
    #             key: value
    #             for key, value in payload_item.items()
    #             if include_key(key)
    #         }
    #
    #         indices = {
    #             key.split("_")[-1]
    #             for key in sgp_details
    #             if key.split("_")[-1].isdigit()
    #         }
    #
    #         return {
    #             "redis_key": payload_item.get("redis_game_key"),
    #             "event": payload_item.get("event"),
    #             "league": payload_item.get("league"),
    #             "date": payload_item.get("date"),
    #             **sgp_details,
    #             "game_keys": [
    #                 payload_item.get(f"game_key_{index}")
    #                 for index in indices
    #             ],
    #             "sgp_odds": valid_odds,
    #             "sgp_links": self._generate_links(payload_item.get("payload", []), sgp_books_with_odds=valid_odds.keys()),
    #             "fair_value": payload_item.get("fair_value"),
    #             "individual_odds_dict": payload_item.get("normal_books"),
    #             "time_fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    #
    #         }
    #
    #     payload_data = payload_data[0:100]
    #
    #     for i in range(0, len(payload_data), batch_size):
    #         batch = payload_data[i:i+batch_size]
    #         print(f"  → Batch {i // batch_size + 1}: {len(batch)} items")
    #         tasks = [fetch_single(item) for item in batch]
    #         results = await asyncio.gather(*tasks)
    #         filtered_results = [result for result in results if result]
    #
    #         if not filtered_results:
    #             print(f"Skipping batch {i // batch_size + 1}")
    #
    #         merged_results = {}
    #
    #         for sgp_data in filtered_results:
    #             data = await self.controller(sgp_data, minimum_ev=minimum_ev)
    #             if not data:
    #                 continue
    #
    #             for key, sub_data in data.items():
    #                 if sub_data:
    #                     merged_results.setdefault(key, {}).update(sub_data)
    #
    #         endpoint_to_store = merged_results.get("endpoint")
    #         if endpoint_to_store:
    #             await self.endpoint_redis.bulk_insert_individual(
    #                 data_to_store=merged_results.get("endpoint", {}),
    #                 pipeline=self.endpoint_redis.redis_client.pipeline(transaction=False)
    #             )
    #
    #         discord_to_store = merged_results.get("discord")
    #         if discord_to_store:
    #             await self.previously_sent_discord_redis.bulk_insert_individual(
    #                 data_to_store=merged_results.get("discord", {}),
    #                 pipeline=self.previously_sent_discord_redis.redis_client.pipeline(transaction=False)
    #             )

    async def get_sgp_odds(self, payload_data: list, session, minimum_ev: float, batch_size: int = 10,
                           retry_times: int = 1):
        mapped_names = {
            book_data.get("mapped_name"): book_data
            for book_data in BOOKS.values()
            if book_data.get("active")
        }

        book_semaphore = asyncio.Semaphore(30)

        async def fetch_single(payload_item: dict):
            tasks = []

            async def run_limited_book(book_cls, book_name):
                async with book_semaphore:
                    return await self.run_sgp_with_retry(
                        book_cls=book_cls,
                        book_name=book_name,
                        retry_times=retry_times,
                        session=session
                    )

            for book in payload_item.get("payload", []):
                book_name = book.get("book_name")
                book_cls_name = mapped_names.get(book_name, {}).get("class")

                if not book_cls_name:
                    print("No Class Found for Book:", book_name)
                    continue

                sgp_data = {
                    "book_name": book_name,
                    "links": book.get("links"),
                    "lines": book.get("lines"),
                    "event_data": book.get("event_data"),
                }

                book_cls = book_cls_name(
                    sgp_data=sgp_data,
                    mapped_ids_redis_instance=self.mapped_ids_redis_instance,
                    auth_redis_instance=self.auth_redis_instance
                )

                tasks.append(run_limited_book(book_cls=book_cls, book_name=book_name))

            results = await asyncio.gather(*tasks)

            valid_odds = {
                book_name: odds_value.get("american_odds")
                for book_name, odds_value in results
                if isinstance(odds_value, dict)
                   and odds_value.get("american_odds") is not None
            }

            if len(valid_odds) <= 1:
                return {}

            def include_key(key: str) -> bool:
                return (
                        (key.startswith("stat_") and key.endswith("_direction")) or
                        key.startswith("stat_name_") or
                        (key.startswith("stat_type_") and key.endswith("_line")) or
                        key.startswith("team_") or
                        key.startswith("market_type_")
                )

            sgp_details = {
                key: value
                for key, value in payload_item.items()
                if include_key(key)
            }

            indices = {
                key.split("_")[-1]
                for key in sgp_details
                if key.split("_")[-1].isdigit()
            }

            return {
                "redis_key": payload_item.get("redis_game_key"),
                "event": payload_item.get("event"),
                "league": payload_item.get("league"),
                "date": payload_item.get("date"),
                **sgp_details,
                "game_keys": [
                    payload_item.get(f"game_key_{index}")
                    for index in indices
                ],
                "sgp_odds": valid_odds,
                "sgp_links": self._generate_links(payload_item.get("payload", []),
                                                  sgp_books_with_odds=valid_odds.keys()),
                "fair_value": payload_item.get("fair_value"),
                "individual_odds_dict": payload_item.get("normal_books"),
                "time_fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            }

        for i in range(0, len(payload_data), batch_size):
            batch = payload_data[i:i + batch_size]
            print(f"  → Batch {i // batch_size + 1}: {len(batch)} items")
            tasks = [fetch_single(item) for item in batch]
            results = await asyncio.gather(*tasks)
            filtered_results = [result for result in results if result]

            if not filtered_results:
                print(f"Skipping batch {i // batch_size + 1}")

            merged_results = {}

            controller_tasks = [
                self.controller(sgp_data, minimum_ev=minimum_ev)
                for sgp_data in filtered_results
            ]
            controller_results = await asyncio.gather(*controller_tasks, return_exceptions=True)

            for data in controller_results:
                if isinstance(data, Exception) or not data:
                    continue

                for key, sub_data in data.items():
                    if sub_data:
                        merged_results.setdefault(key, {}).update(sub_data)

            endpoint_to_store = merged_results.get("endpoint")
            if endpoint_to_store:
                await self.endpoint_redis.bulk_insert_individual(
                    data_to_store=merged_results.get("endpoint", {}),
                    pipeline=self.endpoint_redis.redis_client.pipeline(transaction=False)
                )

            discord_to_store = merged_results.get("discord")
            if discord_to_store:
                await self.previously_sent_discord_redis.bulk_insert_individual(
                    data_to_store=merged_results.get("discord", {}),
                    pipeline=self.previously_sent_discord_redis.redis_client.pipeline(transaction=False)
                )

    async def runner(self):
        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            slips = SlipMapper()

            previous_data = await self.previously_stored_redis_instance.get_all_key_values()
            indexed_previous_data = self.index_previous_data(previous_data)

            for index, filters in enumerate(self.configs, start=1):
                print(
                    f"{'=' * 20}\n[{index}/{len(self.configs)}] Running League: {filters.get('league', 'N/A').upper()}\nStat Types: "
                    f"{', '.join(filters.get('stat_types', []))}",
                )

                espn_mapper = ESPN(filter_data=filters)
                player_mapping = await espn_mapper.runner(
                    session=session,
                    api_caller=self.api_caller
                )

                if not player_mapping:
                    print("No Player Mapping Found. Skipping..")
                    continue

                sportsbook_data = await self._load_sportsbook_data(session, used_stored_json=False, store_json=False)

                if not sportsbook_data:
                    create_sentry_message(
                        tag_key="autosgp",
                        tag_value="bettorodds_data_failure",
                        message="No BettorOdds Data found",
                        level="error"
                    )
                    return

                filtered_data = await self._filter_data(
                    bettorodds_data=sportsbook_data,
                    filter_selection=filters,
                    player_mapping=player_mapping,
                    previous_data=indexed_previous_data,
                    configs=filters
                )

                if not filtered_data:
                    print("No Filtered Data Found. Skipping..")
                    continue

                selection_odds = slips.slip_selection(
                    filtered_data=filtered_data,
                    stat_types=filters.get("stat_types", []),
                    use_same_player=filters.get("use_same_player"),
                    grouped_fields=filters.get("group_fields", []),
                    validate_players=filters.get("validate_players")
                )

                if not selection_odds:
                    print("No Selection Odds Found. Skipping..")
                    continue

                payload_data = self._create_direction_combos(
                    directions=filters.get("direction", ()),
                    selection_odds=selection_odds
                )

                if not payload_data:
                    print("No Payload Data Found. Skipping..")
                    continue

                await self.get_sgp_odds(payload_data, minimum_ev=filters.get("minimum_ev", 15), session=session)








if __name__ == "__main__":
    async def main():
        autosgp = await AutoSGP.create()
        await autosgp.runner()


    asyncio.run(main())