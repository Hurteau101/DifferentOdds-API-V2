import logging
import time
import requests
import os
from Redis.redis_manager import RedisSyncManager
import re
from Settings.book_configurations import BookConfiguration, NAMES_MAPPER
import itertools

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SPREAD_PATTERN = re.compile(r'[+-]\d')


def _input_team(game_details: dict, league: str, espn_mapping: dict):
    """In charge of adding the team name to the game details"""
    player_name = game_details.get("Player")
    split_match = game_details.get("Match", '').split(" vs ")
    stat = game_details.get("Stat", '')

    # Spread Handling
    if SPREAD_PATTERN.search(stat):
        split_short_match = game_details.get("Match Short").split(" vs ")

        if len(split_short_match) != len(split_match):
            team_dict = {}
        else:
            team_dict = dict(zip(split_short_match, split_match))

        team = next((
            team_dict[team_name]
            for team_name in split_short_match
            if team_name.lower().strip() in stat.lower()
        ), None)

        if team:
            game_details["Team"] = team

    # Player handling
    if player_name:
        espn_league = espn_mapping.get(league, {})
        if espn_league:
            team = next((
                team_name
                for team_name, team_data in espn_league.items()
                if player_name.lower() in team_data.get("players", [])
            ), None)

            if team:
                game_details["Team"] = team

    # Fall back.
    if "Team" not in game_details:
        team = next((
            team_name
            for team_name in split_match
            if team_name.lower().strip() in stat.lower()
        ), None)

        if team:
            game_details["Team"] = team

    return game_details

def generate_key(game_details: dict, side: str):
    return "_".join([
        game_details.get("Match"),
        game_details.get("Prop"),
        game_details.get("Unique Stat"),
        side,
        game_details.get("Date")
    ]).replace(" ", "_").replace("-", "_").lower()

def _get_valid_books() -> set:
    categories = set(NAMES_MAPPER.keys())

    books = [
        BookConfiguration.get_book_info(book_type=category, remove_non_active=True,
                                        key_names={"name": "book_key", "alternate_name": "alternate_name", "has_sgp": "has_sgp", "class_instance": "class_instance"})
        for category in categories
    ]

    print(books)

    return set(
        book.get("alternate_name", '').lower()
        if book.get("alternate_name") else book.get("book_key")
        for book in itertools.chain.from_iterable(books)
        if book.get("has_sgp")
    )

def configure_data(bettorodds_data: dict) -> dict:
    """Incharge of adding the team name to the bettorodds data"""
    espn_mapping_redis_instance = RedisSyncManager(database=8)
    espn_mapping = espn_mapping_redis_instance.get_data(key_name="espn_mapping")

    import json
    with open("bettorodds_data_ref.json", "w") as f:
        json.dump(bettorodds_data, f, indent=2)

    if not espn_mapping:
        logging.warning("ESPN mapping not found in Redis. Using default values.")
        return bettorodds_data


    formatted_data = {}

    valid_books = _get_valid_books()
    print(valid_books)

    for game_details in bettorodds_data.values():
        league = game_details.get("League", "N/A")

        _input_team(game_details=game_details, league=league, espn_mapping=espn_mapping)

        book_feed = _extract_book_feed(book_feed=game_details.get("book_feed", {}), stat_type=game_details.get("Prop"), valid_books=valid_books)

        if not book_feed:
            continue

        for side in book_feed:
            formatted_data.setdefault(league, {}).setdefault(game_details.get("Match"), []).append({
                "group_id": game_details.get("Unique ID"),
                "id": generate_key(game_details, side),
                "date": game_details.get("Date"),
                "stat": game_details.get("Prop"),
                "line": game_details.get("Line"),
                "player": game_details.get("Player"),
                "nvig": game_details.get("nvig_map", {}).get(side),
                "team": game_details.get("Team"),
                "side": side,
                "book_feed": book_feed.get(side)
            })


    return formatted_data



def _extract_book_feed(book_feed: dict, stat_type: str, valid_books: set):
    odds = {}

    for book_name, book_directions in book_feed.items():
        if book_name.lower() not in valid_books:
            continue

        has_nested_dict = any(isinstance(value, dict) for value in book_directions.values())

        if not has_nested_dict:
            book_directions = {stat_type: {**book_directions}}

        for side, book_data in book_directions.items():
            american_odds = book_data.get("am_odds")

            if not american_odds or american_odds == "N/A":
                continue

            odds.setdefault(side, [])
            odds[side].append({
                "book_name": book_name,
                "american_odds": american_odds,
                "bet_link": book_data.get("bet_link") if book_data.get("bet_link") else book_data.get(
                    "internal_betlink"),
                "vig": book_data.get("vig_free_odds")
            })

    return odds

def load_bettorodds(limit: str="all", retry_amount: int = 3):
    api_key = os.getenv("INTERNAL_BETTORODDS_API_KEY")
    if not api_key:
        logging.error("No API Key found for BettorOdds. Please set the INTERNAL_BETTORODDS_API_KEY environment variable.")
        return None

    for retry_count in range(retry_amount):
        try:
            response = requests.get(url="https://api.eternity7.dev/api/dev_internal_feed",
                                    headers={"auth_token": api_key, "limit": limit}, timeout=50)

            if response.status_code == 200:
                bettorodds_data = response.json()

                if not bettorodds_data:
                    continue

                bettorodds_data = configure_data(bettorodds_data)

                import json
                with open("bettorodds_data_changed.json", "w") as f:
                    json.dump(bettorodds_data, f, indent=2)

                redis_instance = RedisSyncManager(database=8)
                redis_instance.store_data(
                    key_name="bettorodds_odds",
                    data_to_store=bettorodds_data,
                    key_expiration=120000
                )

                return None

        except requests.RequestException as e:
            logging.error(f"Attempt {retry_count + 1} - Failure in BettorOdds API request: {e}")

        time.sleep(2)
    else:
        logging.error(f"Failed to retrieve data from BettorOdds after {retry_amount} attempts.")
        return None



if __name__ == "__main__":
    load_bettorodds()












#
# import logging
# import time
# import requests
# import os
# from Redis.redis_manager import RedisSyncManager
# import re
# from Settings.book_configurations import BookConfiguration, NAMES_MAPPER
# import itertools
#
# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# logger = logging.getLogger(__name__)
#
# SPREAD_PATTERN = re.compile(r'[+-]\d')
#
# def configure_data(bettorodds_data: dict) -> dict:
#     """Incharge of adding the team name to the bettorodds data"""
#     espn_mapping_redis_instance = RedisSyncManager(database=8)
#     espn_mapping = espn_mapping_redis_instance.get_data(key_name="espn_mapping")
#
#     if not espn_mapping:
#         return bettorodds_data
#
#     formatted_data = {}
#
#     for key, value in bettorodds_data.items():
#         league = value.get("League", "N/A")
#         player_name = value.get("Player")
#         split_match = value.get("Match", '').split(" vs ")
#         stat = value.get("Stat", '')
#
#
#         # Spread Handling
#         if SPREAD_PATTERN.search(stat):
#             split_short_match = value.get("Match Short").split(" vs ")
#
#             if len(split_short_match) != len(split_match):
#                 team_dict = {}
#             else:
#                 team_dict = dict(zip(split_short_match, split_match))
#
#             team = next((
#                 team_dict[team_name]
#                 for team_name in split_short_match
#                 if team_name.lower().strip() in stat.lower()
#             ), None)
#
#             if team:
#                 value["Team"] = team
#
#         # Player handling
#         if player_name:
#             espn_league = espn_mapping.get(league, {})
#             if espn_league:
#                 team = next((
#                     team_name
#                     for team_name, team_data in espn_league.items()
#                     if player_name.lower() in team_data.get("players", [])
#                 ), None)
#
#                 if team:
#                     value["Team"] = team
#
#         # Fall back.
#         if "Team" not in value:
#             team = next((
#                 team_name
#                 for team_name in split_match
#                 if team_name.lower().strip() in stat.lower()
#             ), None)
#
#             if team:
#                 value["Team"] = team
#
#         book_feed = _extract_book_feed(book_feed=value.get("book_feed", {}), stat_type=value.get("Prop"))
#
#         if not book_feed:
#             continue
#
#         formatted_data.setdefault(league, {}).setdefault(value.get("Match"), []).append({
#             "id": value.get("Unique ID"),
#             "date": value.get("Date"),
#             "stat": value.get("Prop"),
#             "normalized_stat": value.get("Stat"),
#             "line": value.get("Line"),
#             "player": value.get("Player"),
#             "team": value.get("Team"),
#             "side": value.get("O/U"),
#             "is_one_way": value.get("one_way"),
#             "nvig_map": value.get("nvig_map", {}),
#             "book_feed": book_feed
#         })
#
#     return formatted_data
#
# def _extract_book_feed(book_feed: dict, stat_type):
#     categories = set(NAMES_MAPPER.keys())
#
#     books = [
#         BookConfiguration.get_book_info(book_type=category, remove_non_active=True,
#                                         key_names={"name": "book_key", "display_name": "display_name"})
#         for category in categories
#     ]
#
#     valid_books = set(
#         book.get("display_name", '').lower() if book.get("display_name") else book.get("book_key")
#         for book in itertools.chain.from_iterable(books)
#     )
#
#     odds = {}
#
#     for book_name, book_directions in book_feed.items():
#         if book_name.lower() not in valid_books:
#             continue
#
#         has_nested_dict = any(isinstance(value, dict) for value in book_directions.values())
#
#         if not has_nested_dict:
#             book_directions = {stat_type: {**book_directions}}
#
#         for side, book_data in book_directions.items():
#             odds.setdefault(book_name, {}).setdefault(side, {})
#             odds[book_name][side].update({
#                 "american_odds": book_data.get("am_odds"),
#                 "bet_link": book_data.get("bet_link") if book_data.get("bet_link") else book_data.get(
#                     "internal_betlink"),
#                 "vig": book_data.get("vig_free_odds")
#             })
#
#     return odds
#
# def load_bettorodds(limit: str="all", retry_amount: int = 3):
#     api_key = os.getenv("INTERNAL_BETTORODDS_API_KEY")
#     if not api_key:
#         logging.error("No API Key found for BettorOdds. Please set the INTERNAL_BETTORODDS_API_KEY environment variable.")
#         return None
#
#     for retry_count in range(retry_amount):
#         try:
#             response = requests.get(url="https://api.eternity7.dev/api/dev_internal_feed",
#                                     headers={"auth_token": api_key, "limit": limit}, timeout=50)
#
#             if response.status_code == 200:
#                 bettorodds_data = response.json()
#
#                 if not bettorodds_data:
#                     continue
#
#                 bettorodds_data = configure_data(bettorodds_data)
#
#                 redis_instance = RedisSyncManager(database=8)
#                 redis_instance.store_data(
#                     key_name="bettorodds_odds",
#                     data_to_store=bettorodds_data,
#                     key_expiration=120000
#                 )
#
#                 return None
#
#         except requests.RequestException as e:
#             logging.error(f"Attempt {retry_count + 1} - Failure in BettorOdds API request: {e}")
#
#         time.sleep(2)
#     else:
#         logging.error(f"Failed to retrieve data from BettorOdds after {retry_amount} attempts.")
#         return None
#
#
#
# if __name__ == "__main__":
#     load_bettorodds()