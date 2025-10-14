import os

from Settings.book_base import BookBase
from abc import ABC
from Settings.sportsbook_config import SportsbookConfig

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

class ExchangeBookBase(BookBase, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory=None, log_name=None):
        self.book_data = SportsbookConfig.get_exchange_provider(sportsbook_name)
        self.redis_db = 1

        if log_directory is None:
            log_directory = os.path.join(PROJECT_ROOT, "Prediction", "Prediction Logs")

        os.makedirs(log_directory, exist_ok=True)

        super().__init__(request_type, log_directory=log_directory, log_name=log_name)