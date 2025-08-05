import asyncio
from abc import ABC, abstractmethod
from dataclasses import asdict
from enum import Enum
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

        if self.request_type == SportbookRequestType.ASYNC:
            if not session or not url:
                raise ValueError("session and url are required for ASYNC calls")
            return await AsyncBook.fetch(session, url, headers)
        elif self.request_type == SportbookRequestType.SPOOF:
            client_identifier = kwargs.get("client_identifier", "chrome_114")
            return await Spoof.fetch(url, headers, client_identifier)
        else:
            raise NotImplementedError(f"Request type {self.request_type} is not supported.")


# Asynchronous book fetching class
class AsyncBook:
    @staticmethod
    async def fetch(session, url, headers=None):
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch data: {response.status} - {await response.text()}")


# Spoofing book fetching class
class Spoof:
    @staticmethod
    async def fetch(api_url, headers=None, client_identifier="chrome_114"):
        import asyncio
        from tls_client import Session

        def _spoof_request():
            session = Session(client_identifier=client_identifier)
            response = session.get(api_url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to fetch data: {response.status_code} - {response.text}")

        return await asyncio.to_thread(_spoof_request)
