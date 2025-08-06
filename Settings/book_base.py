import asyncio
from abc import ABC, abstractmethod
from dataclasses import asdict
from enum import Enum
import asyncio
from tls_client import Session


class SportbookRequestType(Enum):
    ASYNC = "async"
    SPOOF = "spoof"

# This is the base class for all sportsbook books, providing common functionality
class BookBase(ABC):
    def __init__(self, request_type: SportbookRequestType):
        if not isinstance(request_type, SportbookRequestType):
            raise ValueError(
                f"Invalid request type: {request_type}. Valid options are: {', '.join([item.value for item in SportbookRequestType])}."
            )

        self.request_type = request_type

    @staticmethod
    def _generate_key(key_data):
        """Generate a unique key based on the provided data."""
        if key_data is None or not isinstance(key_data, list) or None in key_data:
            return None

        generate_key = sorted(key_data, reverse=True)
        return "_".join([str(key.replace(" ", "_")).lower() for key in generate_key])

    @staticmethod
    def _serialize_data(data):
        """Serialize data to JSON format."""
        return [asdict(player_data) for player_data in data]

    @abstractmethod
    async def run_book(self):
        raise NotImplementedError("Subclasses must implement the run_book method.")

    # Determine the type of API call to make based on the request type
    async def api_caller(self, **kwargs):
        session = kwargs.get("session")
        url = kwargs.get("url")
        headers = kwargs.get("headers")
        method = kwargs.get("method")

        if not url or not method:
            raise ValueError("Both 'url' and 'method' are required for API calls.")

        if self.request_type == SportbookRequestType.ASYNC:
            return await AsyncBook.fetch(session, url, method, headers)
        elif self.request_type == SportbookRequestType.SPOOF:
            client_identifier = kwargs.get("client_identifier", "chrome_114")
            return await Spoof.fetch(url, method, headers, client_identifier)
        else:
            raise NotImplementedError(f"Request type {self.request_type} is not supported.")


# Asynchronous book fetching class
class AsyncBook:
    @staticmethod
    async def fetch(session, url, method, headers=None, **kwargs):
        method = method.lower()
        if method not in ["get", "post"]:
            raise ValueError("Method must be 'get' or 'post'.")

        request_method = getattr(session, method)
        async with request_method(url, headers=headers, **kwargs) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch data: {response.status} - {await response.text()}")


# Spoofing book fetching class
class Spoof:
    @staticmethod
    async def fetch(api_url, method, headers=None, client_identifier="chrome_114", **kwargs):
        def _spoof_request():
            session = Session(client_identifier=client_identifier)
            method_lower = method.lower()

            if method_lower not in ["get", "post"]:
                raise ValueError("Method must be 'get' or 'post'.")

            request_method = getattr(session, method_lower)
            response = request_method(api_url, headers=headers, **kwargs)

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to fetch data: {response.status_code} - {response.text}")

        return await asyncio.to_thread(_spoof_request)