from abc import ABC
from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig
from Settings.Mixin.mixins import ApiResponseMixin

class SGPMapperBase(BookBase, ApiResponseMixin, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory="SGP Logs", log_name=None, key_expiration=800):
        super().__init__(request_type, log_directory, log_name)
        self.book_data = SportsbookConfig.get_sgp_mapper_provider(sportsbook_name)
        self.key_expiration = key_expiration
        self.redis_db = 2

    def check_api_response(self, sportsbook: str, results: list):
        return ApiResponseMixin.check_api_response(self, sportsbook, results)