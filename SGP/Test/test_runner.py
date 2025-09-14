import asyncio
import json
import random
import requests
from dotenv import load_dotenv
import os

from SGP.betmgm import BetMGM_SGP
from SGP.draftkings import Draftkings_SGP
from SGP.fanactics import Fanatics_SGP
from SGP.fanduel import Fanduel_SGP
from SGP.kambi import Kambi_SGP

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')

DEFAULT_CONDITIONS = {
    "league": "NFL",
    "market_types": ["moneyline", "total points"],
}

INITIALIZATION = {
    # "fanduel": Fanduel_SGP,
    # "betmgm": BetMGM_SGP,
    # "fanatics": Fanatics_SGP
    # "kambi": Kambi_SGP
    "draftkings": Draftkings_SGP,
}


class SGPTest:
    def __init__(self, book_data):
        load_dotenv(dotenv_path=env_path)
        self.api_key = os.getenv("bettorodds_api_key")
        self.book_data = book_data
        self.additional_information = []

    def load_odds(self, book_name):
        """Load odds from the bettorodds API for a specific sportsbook."""
        if not self.api_key:
            raise ValueError("API key is not set. Please set the bettorodds_api_key in your .env file.")

        url = f"https://api.eternity7.dev/api/internal_odds?sportsbook={book_name}"
        response = requests.get(url, params={"auth_token": self.api_key})
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def _default_filter_data(self, book_data):
        """Filter the bettorodds data based on default conditions."""
        default_data = DEFAULT_CONDITIONS

        league_filter = list(
            filter(lambda x: x.get("backend_extras").get("league") == default_data.get("league"), book_data))

        if not league_filter:
            raise ValueError(f"No data found for league: {default_data.get('league')}")

        league_length = len(league_filter)
        random_game = random.randint(0, league_length - 1)

        game_name = league_filter[random_game].get("backend_extras").get("event")

        results = []

        for market in default_data["market_types"]:
            match = next(
                (entry for entry in league_filter
                 if entry.get("Market", "").lower() == market.lower()
                 and entry.get("backend_extras", {}).get("event") == game_name),
                None
            )

            if match:
                results.append({
                    "market": market,
                    "link": match.get("backend_extras", {}).get("betlink") if match.get("backend_extras", {}).get("betlink") else match.get("backend_extras", {}).get("internal_betlink"),
                    "event": game_name,
                    "book": match.get("SportsBook"),
                    "bet_info": match.get("Bet Info")
                })

        self.additional_information.extend(results)
        return [link.get("link") for link in results if link.get("link")]




    def _map_data(self):
        """Map the book data to the appropriate sportsbook classes and load odds."""
        books = []

        for book in self.book_data:
            book_name = book.get("book_name").lower()
            links = book.get("links", [])

            if book_name not in INITIALIZATION:
                raise ValueError(f"Unsupported book name: {book_name}")

            book_data = self.load_odds(book_name)

            if not links:
                book["links"] = self._default_filter_data(book_data)

            book_obj = INITIALIZATION[book_name](links=book["links"])
            book_obj.book_name = book_name
            books.append(book_obj)

        return books


    async def run_test(self, json_name="test_data.json", json_path=None, indent=2):
        if not self.book_data:
            raise ValueError("No book data provided for testing.")

        books = self._map_data()
        tasks = [book.run_book() for book in books]

        results = await asyncio.gather(*tasks)

        # Filter out None results and map them to book names
        results = [
            {"book_name": book.book_name, "result": result}
            for book, result in zip(books, results)
            if result
        ]

        # Add additional information to each result
        test_data = [
            {
                **result,
                "additional_info": [
                    additional for additional in self.additional_information
                    if result.get("book_name").lower() == additional.get("book", "").lower()
                ]
            }
            for result in results
        ]

        if json_path and os.path.isdir(json_path):
            json_path = os.path.join(json_path, json_name)
        else:
            json_path = os.path.join(os.path.dirname(__file__), json_name)

        if not test_data:
            error_data = {
                "message": "No valid test data generated. Please check the information provided. Ensure that the "
                           "book data is correct and that the links are valid.Here is the data passed in",
                "book_data": self.book_data,
                "additional_information": self.additional_information
            }
            data_to_write = error_data
        else:
            data_to_write = test_data

        message_to_display = "• Test data generated successfully. \n" \
            if test_data else ("• No valid test data generated.\n"
                               "• If FanDuel data is empty, ensure that you have a locally redis running to store the "
                               "mapped ids.\n")

        message_to_display += f"• Please check {json_path} for the output."

        print(message_to_display)

        with open(json_path, "w") as file:
            json.dump(data_to_write, file, indent=indent)


if __name__ == "__main__":
    ################ SAMPLE RUN ################
    # book_data = [
    #     {"book_name": "Fanduel", "links": []}
    # ]
    # test_instance = SGPTest(book_data)
    # asyncio.run(test_instance.run_test())
    ############################################

    # book_data = [
    #     {"book_name": "Fanduel", "links": []}
    # ]
    book_data = [
        {"book_name": "draftkings", "links": []}
    ]

    test_instance = SGPTest(book_data)
    asyncio.run(test_instance.run_test())