import os
from dotenv import load_dotenv
import requests
import re

class BettorOdds:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("bettorodds_api_key")

    def _get_odds(self):
        url = "https://api.eternity7.dev/api/internal_odds?"
        params = {
            "auth_token": self.api_key,
            "sportsbook": "novig",
        }

        response = requests.request("GET", url, params=params)
        if response.status_code == 200:
            return response.json()

        return None

    def _extract_key(self, key_id):
        event_id = re.search(r"events/([^/]+)", key_id)
        if event_id:
            return event_id.group(1)

        return None

    def _extract_other_book_details(self, book_details):
        result = {}

        for item in book_details:
            try:
                book, rest = item.split(" [", 1)
                book = book.strip()

                left, right = rest.split("||")
                left = left.strip("[] ").split()
                right = right.strip("[] ").split()

                left_label = " ".join(left[:-1])
                left_odds = int(left[-1])
                right_label = " ".join(right[:-1])
                right_odds = int(right[-1])

                result[book] = {
                    left_label: left_odds,
                    right_label: right_odds
                }

            except Exception:
                continue

        return result
    def _filter_data(self, raw_data):
        return {
            event_id: {
                "market": data.get("Market"),
                "bet_info": data.get("Bet Info"),
                "league": data.get("backend_extras", {}).get("league"),
                "event": data.get("backend_extras", {}).get("event"),
                "short_event": data.get("backend_extras", {}).get("event_short"),
                "date": data.get("backend_extras", {}).get("raw_date"),
                "odds": self._extract_other_book_details(data.get("Book Details", []))
            }

            for data in raw_data
            if (event_id := self._extract_key(data.get("backend_extras", {}).get("betlink")))
        }

    def run_bettorodds(self):
        raw_odds = self._get_odds()
        if raw_odds:
            filtered_data = self._filter_data(raw_odds)
            if filtered_data:
                return filtered_data

            # import json
            # with open("bettorodds_odds.json", "w") as f:
            #     json.dump(filtered_data, f, indent=4)




if __name__ == "__main__":
    bettor = BettorOdds()
    bettor.run_bettorodds()