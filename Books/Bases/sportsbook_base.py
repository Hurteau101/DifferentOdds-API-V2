from Books.Bases.book_base import BookBase
from Utils.request_caller import SportbookRequestType


class SportsbooksBookBase(BookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(category="sportsbooks", book_name=book_name, request_type=request_type, redis_database=6)

    async def external_mapper(self, sportsbook_data: list):
        pass