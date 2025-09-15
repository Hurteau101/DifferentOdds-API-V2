import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict
from enum import Enum
import asyncio
from functools import lru_cache
from tls_client import Session
from dateutil import parser
from Settings.logger import FileLogger, ConsoleLogger
import pytz

class SportbookRequestType(Enum):
    ASYNC = "async"
    SPOOF = "spoof"

# This is the base class for all sportsbook books, providing common functionality
class BookBase(ABC):
    def __init__(self, request_type: SportbookRequestType, log_directory=None, log_name=None):
        if not isinstance(request_type, SportbookRequestType):
            raise ValueError(
                f"Invalid request type: {request_type}. Valid options are: {', '.join([item.value for item in SportbookRequestType])}."
            )

        self.request_type = request_type
        self._create_directory(log_directory)

        if log_name is None:
            log_name = f"{self.__class__.__name__}.log"

        log_path = os.path.join(log_directory, log_name)

        self.file_logger = FileLogger(log_path)
        self.console_logger = ConsoleLogger()

    def _create_directory(self, directory: str):
        """Create a directory if it doesn't exist."""
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _api_call_log(self, sportsbook_name):
        """General logger for when a sportsbook can't get data from API"""
        self.file_logger.log(
            message=f"Failed to fetch data from {sportsbook_name} API",
            level="ERROR",
        )

    @staticmethod
    def _generate_key(key_data):
        """Generate a unique key based on the provided data."""
        if key_data is None or not isinstance(key_data, list) or None in key_data:
            return None

        generate_key = sorted(key_data, reverse=True)
        return "_".join([str(key.replace(" ", "_")).lower() for key in generate_key])

    @staticmethod
    def convert_time(date_time_str):
        """Convert the date to UTC format"""
        if date_time_str is None:
            return None

        dfs_time = parser.parse(date_time_str)
        utc_time = dfs_time.astimezone(pytz.utc)

        return utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    @lru_cache(maxsize=1000)
    def cache_time(self, date_time_str):
        """Convert the date to UTC format and cache the result"""
        return self.convert_time(date_time_str)

    @staticmethod
    def serialize_data(data):
        """Serialize data to JSON format."""
        return [asdict(player_data) for player_data in data]

    @staticmethod
    def _split_teams(game_title):
        """Split teams from the game title."""
        split_operators = [" vs ", " @ "]

        for operator in split_operators:
            if operator in game_title:
                parts = game_title.split(operator)
                if len(parts) == 2:
                    team_a, team_b = sorted([parts[0].strip(), parts[1].strip()])
                    return {
                        "team_a": team_a,
                        "team_b": team_b,
                        "operator": operator.strip()
                    }

        return None

    @staticmethod
    def create_json(data, file_name):
        """Create a JSON file from the provided data."""
        with open(file_name, "w") as json_file:
            json.dump(data, json_file, indent=2)

    @abstractmethod
    async def run_book(self):
        raise NotImplementedError("Subclasses must implement the run_book method.")

    # Determine the type of API call to make based on the request type
    async def api_caller(self, **kwargs):
        session = kwargs.get("session")
        url = kwargs.get("url")
        headers = kwargs.get("headers")
        method = kwargs.get("method")
        proxy = kwargs.get("proxy")
        payload = kwargs.get("payload")
        parse_json = kwargs.get("parse_json", False)
        params = kwargs.get("params")

        if not url or not method:
            raise ValueError("Both 'url' and 'method' are required for API calls.")

        if self.request_type == SportbookRequestType.ASYNC:
            return await AsyncBook.fetch(session, url, method, headers, proxy, payload, parse_json, params)
        elif self.request_type == SportbookRequestType.SPOOF:
            client_identifier = kwargs.get("client_identifier", "chrome_114")
            return await Spoof.fetch(url, method, headers, client_identifier, proxy, payload, params)
        else:
            raise NotImplementedError(f"Request type {self.request_type} is not supported.")


# Asynchronous book fetching class
class AsyncBook:
    @staticmethod
    async def fetch(session, url, method, headers=None, proxy=None, payload=None, parse_json=False, params=None, data=None):
        method = method.lower()
        if method not in ["get", "post"]:
            raise ValueError("Method must be 'get' or 'post'.")

        request_method = getattr(session, method)

        if method == "get":
            async with request_method(url, headers=headers, proxy=proxy, params=params) as response:
                return await AsyncBook._handle_response(response, parse_json=parse_json)
        else:
            async with request_method(url, headers=headers, proxy=proxy, json=payload) as response:
                return await AsyncBook._handle_response(response, parse_json=parse_json)

    @staticmethod
    async def _handle_response(response, parse_json):
        """Handle the response from the API call."""
        if response.status in [200, 201]:
            # Some API's return text that needs to be parsed as JSON
            if parse_json:
                try:
                    text = await response.text()
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None

            return await response.json()
        else:
            return None



# Spoofing book fetching class
class Spoof:
    @staticmethod
    async def fetch(api_url, method, headers=None, payload=None, client_identifier="chrome_114", proxy=None, params=None):
        def _spoof_request():
            session = Session(client_identifier=client_identifier)
            method_lower = method.lower()

            if method_lower not in ["get", "post"]:
                raise ValueError("Method must be 'get' or 'post'.")

            request_method = getattr(session, method_lower)

            if method_lower == "get":
                response = request_method(api_url, headers=headers, proxy=proxy, params=params)
            else:
                response = request_method(api_url, headers=headers, proxy=proxy, json=payload)

            if response.status_code == 200:
                return response.json()
            else:
                return None

        return await asyncio.to_thread(_spoof_request)