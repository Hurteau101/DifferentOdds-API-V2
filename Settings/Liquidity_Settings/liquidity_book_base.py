from Settings.Mixin.mixins import ApiResponseMixin
from Settings.book_base import BookBase
from abc import ABC, abstractmethod

from Settings.sportsbook_config import SportsbookConfig


class LiquidityBookBase(ApiResponseMixin, BookBase, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory="Liquidity Logs", log_name="Liquidity", **kwargs):
        self.book_data = SportsbookConfig.get_liquidity_provider(sportsbook_name)
        super().__init__(request_type, log_directory=log_directory, log_name=log_name, **kwargs)



