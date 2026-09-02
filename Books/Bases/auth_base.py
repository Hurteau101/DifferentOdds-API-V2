from abc import abstractmethod
from Books.Bases.book_base import BookBase

class AuthBase(BookBase):
    def __init__(self, category: str, book_name: str, redis_expiration: int = 800):
        super().__init__(book_category=category, book_name=book_name, redis_database=1, redis_expiration=redis_expiration)
        self.auth_id_name = self.book_data.auth_job_dict.auth_redis_key

        if not self.auth_id_name:
            raise KeyError(f"Ensure {self.book_data.name} has a 'mapper_redis_key'")

    @abstractmethod
    async def run_auth(self) -> bool:
        raise NotImplementedError("Subclasses must implement the run_auth method.")
