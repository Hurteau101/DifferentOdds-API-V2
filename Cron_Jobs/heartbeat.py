import os
from enum import Enum
from discordwebhook import Discord
from dotenv import load_dotenv
from APScheduler.scheduler_runner import AUTH_JOBS, MAPPER_JOBS
from Monitoring.Discord_Logging.logger import send_discord_message
from Redis.redis_manager import RedisSyncManager
from Settings.book_configurations import BookConfiguration
from datetime import datetime, timezone, timedelta
from Utils.helpers import is_production

load_dotenv()


class RedisDatabaseMapper(Enum):
    DFS = 0
    SPORTSBOOKS = 6
    AUTH = 5
    MAPPER = 2

    def return_redis(self):
        return RedisSyncManager(database=self.value)


class HeartBeat:
    CATEGORIES = [
        "DFS", "SPORTSBOOKS"
    ]

    WEBHOOK_URL = os.getenv("DISCORD_HEARTBEAT_URL")
    TML_USER_ID = os.getenv("TML_USER_ID")

    if not WEBHOOK_URL:
        raise ValueError("DISCORD_HEARTBEAT_URL environment variable not set")

    if not TML_USER_ID:
        raise ValueError("TML_USER_ID environment variable not set")


    def __init__(self):
        self.books = {}
        self.discord_bot = Discord(url=self.WEBHOOK_URL)
        self.run_setup()

    def run_setup(self):
        for category in self.CATEGORIES:

            book_list = BookConfiguration.get_book_info(book_type=category)
            filtered_books = [
                book.get("book_key")
                for book in book_list
                if book.get("status") is True
            ]

            redis = RedisDatabaseMapper.DFS.return_redis() if category == "DFS" else RedisDatabaseMapper.SPORTSBOOKS.return_redis()
            redis_db_num = RedisDatabaseMapper.DFS.value if category == "DFS" else RedisDatabaseMapper.SPORTSBOOKS.value

            book_names = [{"book_name": book, "book_key": f"{book}:game", "redis": redis, "db_num": redis_db_num} for book in
                          filtered_books]

            self.books[category] = book_names

        self._configure_mapper_auth()

    def _configure_mapper_auth(self):
        """Configures the book list for mapper and auth, as they are a bit different, and using an import from another file"""
        redis_auth = RedisDatabaseMapper.AUTH.return_redis()
        redis_auth_db_number = RedisDatabaseMapper.AUTH.value
        mapper_auth = RedisDatabaseMapper.MAPPER.return_redis()
        redis_mapp_db_number = RedisDatabaseMapper.MAPPER.value

        auth_books = [
            {
                "book_name": book.get("book_name"),
                "book_key": book.get("redis_key_checker_name"),
                "redis": redis_auth,
                "db_num": redis_auth_db_number
            }
            for book in AUTH_JOBS
            if book.get("is_active")
        ]

        map_books = [
            {
                "book_name": book.get("book_name"),
                "book_key": book.get("redis_key_checker_name"),
                "redis": mapper_auth,
                "db_num": redis_mapp_db_number
            }
            for book in MAPPER_JOBS
            if book.get("is_active")
        ]

        self.books["MAPPER"] = map_books
        self.books["AUTH"] = auth_books

    def store_key(self, display_name: str, category: str, sent_already_instance: RedisSyncManager, actual_redis_key_name: str,
                  retry_amount: int, sent_already_key_name: str, redis_actual_key_db: int):

        send_discord_message(
            self.discord_bot,
            severity=1,
            title=f"{display_name.title()}",
            description="Heart Beat Failure - Couldn't find the redis key. Please investigate.",
            multiple_fields=True,
            fields=[
                {
                    "name": "Category",
                    "value": category.upper(),
                },
                {
                    "name": "Redis Key",
                    "value": actual_redis_key_name,
                },
                {
                    "name": "Redis DB",
                    "value": str(redis_actual_key_db),
                },
                {
                    "name": "Remaining Retries",
                    "value": str(3 - int(retry_amount)),
                }
            ],
            should_tag=True,
            tag_id=self.TML_USER_ID
        )

        sent_already_instance.store_data(
            key_name=sent_already_key_name,
            data_to_store={
                "retry_amount": retry_amount + 1,
                "last_sent": datetime.now(tz=timezone.utc).isoformat()
            },
            key_expiration=86400, # 1 Day
        )


    def check_keys(self):
        sent_db = 14 if is_production() else 17

        sent_already_instance = RedisSyncManager(database=sent_db)

        for main_key, book_info in self.books.items():
            for book_data in book_info:

                book_name_display = book_data.get("book_name") # Name of the book for display purposes.
                actual_redis_key_name = book_data.get("book_key") # The name of the key to check. Used to determine if a book isn't storing data properly.
                sent_already_key_name = f"{book_name_display.lower()}-{main_key.lower()}"
                actual_redis_db = book_data.get("db_num")

                actual_redis_book_data = book_data.get("redis").get_data(actual_redis_key_name) # Check if the book has any data in redis.

                if not actual_redis_book_data:
                    in_redis_sent_cache = sent_already_instance.get_data(sent_already_key_name)

                    if not in_redis_sent_cache:
                        self.store_key(
                            display_name=book_name_display,
                            category=main_key,
                            sent_already_instance=sent_already_instance,
                            actual_redis_key_name=actual_redis_key_name,
                            retry_amount=1,
                            sent_already_key_name=sent_already_key_name,
                            redis_actual_key_db=actual_redis_db
                        )

                        continue

                    retry_amount = in_redis_sent_cache.get("retry_amount", 99)
                    last_sent = in_redis_sent_cache.get("last_sent", None)

                    if not last_sent:
                        raise ValueError("last_sent is not found in the sent cache, but it should be.")

                    last_sent_dt = datetime.fromisoformat(last_sent)
                    current_date = datetime.now(tz=timezone.utc)

                    if all([
                        in_redis_sent_cache,
                        retry_amount < 4,
                        current_date - last_sent_dt > timedelta(minutes=30)
                    ]):

                        self.store_key(
                            display_name=book_name_display,
                            category=main_key,
                            sent_already_instance=sent_already_instance,
                            actual_redis_key_name=actual_redis_key_name,
                            retry_amount=retry_amount,
                            sent_already_key_name=sent_already_key_name,
                            redis_actual_key_db=actual_redis_db
                        )
                else:
                    sent_already_instance.delete_data(sent_already_key_name)



if __name__ == "__main__":
    heartbeat = HeartBeat()
    heartbeat.check_keys()





