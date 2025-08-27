import re
from abc import ABC, abstractmethod
from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig


class SGPBookBase(BookBase, ABC):
    """Base class for SGP books, inheriting from SportsbookBase."""
    def __init__(self, request_type, sportsbook_name: str, links, log_directory="SGP Logs", log_name=None):
        self.book_data = SportsbookConfig.get_sgp_provider(sportsbook_name)
        self.link_data = self._extract_link_details(links)
        self.redis_db = 2
        super().__init__(request_type, log_directory=log_directory, log_name=log_name)


    @abstractmethod
    async def run_book(self):
        """Run the SGP book logic."""
        pass


    @staticmethod
    def require_link_data(func):
        """Decorator to ensure there is link data before running the function."""
        async def wrapper(self):
            if not getattr(self, "link_data", None):
                return None
            return await func(self)
        return wrapper

    def _extract_link_details(self, links):
        """ Extract bet_id and event_id from the provided links."""
        link_data = []

        for link in links:
            if not link:
                return None

            bet_id = re.search(self.book_data.regex.get("bet_id_regex"), link)
            event_id = re.search(self.book_data.regex.get("event_id_regex"), link)
            if bet_id and event_id:
                bet_id = bet_id.group(1)

                link_data.append({
                    "bet_id": bet_id,
                    "event_id": event_id.group(1)
                })

        return link_data if link_data else None


