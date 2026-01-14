from Settings.Mixin.mixins import ApiResponseMixin
from Settings.book_base import BookBase
from abc import ABC, abstractmethod
from Settings.sportsbook_config import SportsbookConfig


class SportsbookBase(BookBase, ApiResponseMixin, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory="Sportsbook Logs", log_name=None):
        self.book_data = SportsbookConfig.get_sportsbook_provider(sportsbook_name)
        super().__init__(request_type, sportsbook_name=sportsbook_name, log_directory=log_directory, log_name=log_name)

    def check_api_response(self, sportsbook: str, results: list):
        return ApiResponseMixin.check_api_response(self, sportsbook, results)

    @abstractmethod
    async def run_book(self):
        """Run the SGP book logic."""
        pass

