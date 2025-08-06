from abc import abstractmethod, ABC
from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig
from Settings.logger import FileLogger, ConsoleLogger
import os
from dfs_model import PlayerData

class DFSBookBase(BookBase, ABC):
    """Base class for DFS books, inheriting from BookBase."""
    def __init__(self, request_type, sportsbook_name: str, log_directory: str = "DFS Logs", log_name: str = None):
        self.book_data = SportsbookConfig.get_dfs_provider(sportsbook_name)
        super().__init__(request_type)
        self._create_directory(log_directory)

        if log_name is None:
            log_name = f"{self.__class__.__name__}.log"

        log_path = os.path.join(log_directory, log_name)
        FileLogger.set_log_file(log_path)

        self.file_logger = FileLogger()
        self.console_logger = ConsoleLogger()


    def _create_directory(self, directory: str):
        """Create a directory if it doesn't exist."""
        if not os.path.exists(directory):
            os.makedirs(directory)


    def _database_mapper(self, sportsbook_data: PlayerData):
        pass



#### EXAMPLE CALLS
### SPOOF
# api_data = await self.api_caller(
#     url=self.book_data.url.get("main_url"),
#     method=self.book_data.method,
#     client_identifier="chrome_114"  # or whichever spoof client you want
# )

### ASYNC
# async with aiohttp.ClientSession() as session:
    #     api_data = await self.api_caller(
    #         session=session,
    #         url=self.book_data.url.get("main_url"),
    #         method=self.book_data.method
    #     )

