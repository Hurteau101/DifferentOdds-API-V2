import logging
import time
import requests
import os
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Redis.redis_manager import RedisSyncManager
import re
from Settings.book_configurations import BookConfiguration
import itertools
from Utils.helpers import clean_and_normalize
from Books.Bases.mapper_base import MapperBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SPREAD_PATTERN = re.compile(r'[+-]\d')


def _input_team(game_details: dict, league: str, espn_mapping: dict, split_match: list):
    """In charge of adding the team name to the game details"""
    player_name = clean_and_normalize(game_details.get("Player", ''))
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
    books = [
        BookConfiguration.get_book_info(book_type="sgp", remove_non_active=True,
                                        key_names={"name": "book_key", "alternate_name": "alternate_name", "has_sgp": "has_sgp", "class_instance": "class_instance"})
    ]

    return set(
        book.get("book_key")
        for book in itertools.chain.from_iterable(books)
    )

def _load_underdog(prop_key: str, underdog_data: dict, feed: dict) -> dict | None:
    if not all([prop_key, underdog_data, feed]):
        return None

    found = next((
        odds
        for item in underdog_data.get("data", [])
        for odds in item.get("odds", [])
        if odds.get("prop_key") == prop_key
    ), None)

    if not found:
        return None

    feed.update({
        "underdog": {
            "american_odds": found.get("odds_format", {}).get("american_odds"),
            "bet_link": '',
        }
    })


def _load_prop_builder(event_key: str, prop_key: str, prop_builder_ids: dict, feed: dict):
    if not all([event_key, prop_key, prop_builder_ids, feed]):
        return

    found = prop_builder_ids.get(event_key, {}).get(prop_key, {})

    if not found:
        return

    feed.update({
        "prop builder": {
            "american_odds": found.get("american_odds"),
            "bet_link": '',
        }
    })

def configure_data(bettorodds_data: dict) -> dict:
    """Incharge of adding the team name to the bettorodds data"""
    espn_mapping_redis_instance = RedisSyncManager(database=8)
    espn_mapping = espn_mapping_redis_instance.get_data(key_name="espn_mapping")

    if not espn_mapping:
        insert_log(
            book_name="espn_mapping",
            error_type=ErrorTypes.ESPN_NO_DATA,
            error_message="No ESPN mapping found in Redis."
        )

        return bettorodds_data

    mapping_redis_instance = RedisSyncManager(database=2)
    book_redis_instance = RedisSyncManager(database=0)
    prop_builder_ids = mapping_redis_instance.get_data(key_name="prop_builder_mapped_ids")
    underdog_data = book_redis_instance.get_data(key_name="underdog:base")

    formatted_data = {}

    valid_books = _get_valid_books()

    for game_details in bettorodds_data.values():
        league = game_details.get("League", "N/A")
        split_match = game_details.get("Match", '').split(" vs ")

        normalized_date = game_details.get("Date", '').replace(" ", "T")

        _input_team(game_details=game_details, league=league, espn_mapping=espn_mapping, split_match=split_match)

        book_feed = _extract_book_feed(book_feed=game_details.get("book_feed", {}), stat_type=game_details.get("Prop"), valid_books=valid_books)

        if not book_feed:
            continue

        sorted_match_name = ' vs '.join(sorted(split_match)).lower()
        event_key = f"{sorted_match_name}_{normalized_date.lower()}".replace(" ", "_")
        player = game_details.get("Player", '')
        line = game_details.get("Line", '')
        prop = game_details.get("Prop", '')


        for side in book_feed:
            normalized_raw = f"{player} {side} {line} {prop}"
            unique_stat = f"{game_details.get('Player', '')} {game_details.get('Prop', '').replace('Player', '')}"
            prop_key = MapperBase.build_prop_key(stat=prop, side=side, line=line, player=player)

            feed = book_feed.get(side)

            _load_prop_builder(
                event_key=event_key,
                prop_key=prop_key,
                prop_builder_ids=prop_builder_ids,
                feed=feed
            )

            _load_underdog(
                prop_key=prop_key,
                underdog_data=underdog_data,
                feed=feed
            )

            # Do after prop builder, as we want the player removed in normalize.
            normalized_raw = normalized_raw.replace('Player', '').strip()

            formatted_data.setdefault(league, {}).setdefault(game_details.get("Match"), []).append({
                "group_id": game_details.get("Unique ID"),
                "id": generate_key(game_details, side),
                "unique_stat": re.sub(r"\s+", " ", unique_stat).strip(),
                "normalized_name": re.sub(r"\s+", " ", normalized_raw).strip(),
                "prop_key": prop_key,
                "event_key": event_key,
                "date": normalized_date,
                "stat": game_details.get("Prop"),
                "line": game_details.get("Line"),
                "player": game_details.get("Player"),
                "nvig": game_details.get("nvig_map", {}).get(side),
                "team": game_details.get("Team"),
                "side": side,
                "book_feed": feed
            })


    return formatted_data



def _extract_book_feed(book_feed: dict, stat_type: str, valid_books: set):
    odds = {}

    for book_name, book_directions in book_feed.items():
        book_name = book_name.lower()

        if book_name not in valid_books:
            continue

        has_nested_dict = any(isinstance(value, dict) for value in book_directions.values())

        if not has_nested_dict:
            book_directions = {stat_type: {**book_directions}}

        for side, book_data in book_directions.items():
            american_odds = book_data.get("am_odds")

            if not american_odds or american_odds == "N/A":
                continue

            odds.setdefault(side, {})
            odds[side].update({
                book_name: {
                    "american_odds": american_odds,
                    "bet_link": book_data.get("bet_link") if book_data.get("bet_link") else book_data.get(
                        "internal_betlink"),
                    "vig": book_data.get("vig_free_odds")
                }
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

                redis_instance = RedisSyncManager(database=6)
                redis_instance.store_data(
                    key_name="bettorodds_odds",
                    data_to_store=bettorodds_data,
                    key_expiration=360
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