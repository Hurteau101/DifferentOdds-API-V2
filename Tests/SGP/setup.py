from datetime import datetime, timedelta
import random

import requests
from dotenv import load_dotenv
import os
import json
from Settings.Providers.SGP.sgp_providers import SGP_PROVIDERS
from Tests.common_test_helper import create_json_file

load_dotenv()

class SGPSetUp:
    SUPPORTED_SGP_BOOKS = [provider.name for provider in SGP_PROVIDERS]
    def __init__(self, markets: list, league: str):
        self.markets = markets
        self.league = league
        self.retry = 0

    def use_stored_data(self, json_file_name: str = "internal_odds_data.json"):
        current_directory = os.getcwd()
        path = os.path.join(current_directory, json_file_name)

        if os.path.exists(path):
            with open(path, "r") as json_file:
                data = json.load(json_file)
                last_update = data.get("run_time")
                last_update_date_obj = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S").date() if last_update else None

                current_date = datetime.today().date()
                if abs((current_date - last_update_date_obj).days) >= 1:
                    print("Stored data is older than one day. Consider fetching new data.")

                return data.get("internal_odds")

        raise FileNotFoundError("Stored JSON file not found. Please re-run and set used_stored_data to False and should_store_internal to "
                                "True if you want to use previously fetched data.")

    def get_internal_odds(self, limit: int | str = "all", store_json: bool = False, json_file_name: str = "internal_odds"):
        """Fetch internal odds data from BettorOdds Dev API"""
        url = "https://api.eternity7.dev/api/dev_internal_feed"
        headers = {
            "auth_token": os.getenv("INTERNAL_BETTORODDS_API_KEY"),
            "limit": str(limit)
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            response_data = response.json()

            if store_json:
                json_file_name.replace(".json", "")

                current_directory = os.getcwd()
                create_json_file(current_directory, json_file_name, response_data)

            return response_data

        return None

    def filter_data(self, internal_odds: dict, league: str, market_names: list):
        """Filter internal odds data by league and market names."""
        return {
            key_name: odds_data
            for key_name, odds_data in internal_odds.items()
            if odds_data.get("League", "").lower() == league.lower() and odds_data.get("Prop", "") in market_names
        }

    def create_valid_book_feed(self, book_feed_dict: dict) -> dict:
        """Create a valid book feed dictionary with supported books and available bet links."""
        feed = {}

        for book_name, book_feed in book_feed_dict.items():
            if book_name.lower() in SGPSetUp.SUPPORTED_SGP_BOOKS:
                links = {}
                for side, details in book_feed.items():
                    if details.get("betlink"):
                        links.update({
                            side: details.get("betlink")
                        })
                if links:
                    feed[book_name.lower()] = links
        return feed

    def group_matches(self, filtered_odds: dict):
        """Group matches by event name and date."""
        events = {}
        for odds in filtered_odds.values():
            event_name = odds.get("Match").replace(" ", "_").lower()
            date = odds.get("Date").replace(" ", "_").lower()
            key = "_".join([event_name, date])
            stat_type = odds.get("Prop")

            valid_feeds = self.create_valid_book_feed(odds.get("book_feed"))

            if key not in events:
                events[key] = {}

            if stat_type not in events[key]:
                events[key][stat_type] = []

            data = {
                "stat_name": odds.get("Unique Stat"),
                "book_feed": valid_feeds,
            }

            events[key][stat_type].append(data)

        return events

    def create_pairings(self, grouped_filter: dict, book_name: str = "draftkings"):
        """Create pairings of stats for SGPs."""
        if self.retry > 2:
            raise ValueError(f"Maximum retry attempts reached for creating pairings. {book_name}")

        pairings = {}
        games = set(grouped_filter.keys())
        random_game = random.choice(list(games))
        market_names = set(
            market_name
            for market_name, _ in grouped_filter[random_game].items()
        )

        if len(market_names) < 2:
            raise ValueError("Not enough market names to create pairings.")

        market_lengths = {}

        for market in market_names:
            market_lengths[market] = len(grouped_filter[random_game][market])

        for market_name, length in market_lengths.items():
            random_index = random.randint(0, length - 1)
            grab_random = grouped_filter[random_game][market_name][random_index]

            if book_name.lower() not in grab_random["book_feed"]:
                self.retry += 1
                return self.create_pairings(grouped_filter, book_name=book_name)

            if book_name not in pairings:
                pairings[book_name] = {
                    "book_name": book_name,
                    "links": []
                }

            pairings[book_name]["links"].append(
                next(iter(grab_random["book_feed"][book_name].values()))
            )

        self.retry = 0
        return pairings[book_name]

    def return_valid_books(self, exclude_list: list = None):
        return ["draftkings", "prophetx"]
        # return [
        #     book for book in SGPSetUp.SUPPORTED_SGP_BOOKS
        #     if book.lower() not in ([exclude.lower() for exclude in exclude_list] if exclude_list else [])
        # ]

    def run_startup(self, used_stored_data: bool = False, should_store_internal: bool = True, should_store_filtered: bool = True):
        odds = self.get_internal_odds(store_json=should_store_internal) if not used_stored_data else self.use_stored_data()
        filtered = self.filter_data(odds, self.league, self.markets)
        group_filtered = self.group_matches(filtered)

        if should_store_filtered:
            create_json_file(os.getcwd(), "filtered_sgp", group_filtered)
        return group_filtered


if __name__ == "__main__":
    MARKETS = ["Player Made Threes", "Moneyline"]
    LEAGUE = "NBA"

    setup = SGPSetUp(markets=MARKETS, league=LEAGUE)
    setup.run_startup(used_stored_data=False, should_store_filtered=False, should_store_internal=True)
