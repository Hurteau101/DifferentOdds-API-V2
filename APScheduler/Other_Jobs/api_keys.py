from sqlalchemy.orm import sessionmaker
from Database.base_db import sync_engine
from Redis.redis_manager import RedisSyncManager
from Database.API.api_db import APIKeys

def store_api_keys():
    session = sessionmaker(bind=sync_engine())
    with session() as db_session:
        api_keys = APIKeys.get_api_keys(db_session)

    redis_instance = RedisSyncManager(database=7)

    redis_instance.store_data(
        key_name="api_keys",
        data_to_store=api_keys,
        key_expiration=3600  # 1 Hour
    )

if __name__ == "__main__":
    store_api_keys()




