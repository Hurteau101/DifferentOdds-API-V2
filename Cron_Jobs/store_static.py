"""Used to store static data into Redis Database"""
from sqlalchemy.orm import sessionmaker
from Database.base_db import sync_engine
from Redis.redis_manager import RedisSyncManager
from Database.Sportsbooks.sportsbook_db import LeagueMapper, StatMapper

def store_static():
    redis_instance = RedisSyncManager(database=7)
    engine = sync_engine()
    Session = sessionmaker(bind=engine)

    with Session() as session:
        static_mapping = StatMapper.get_mapping(db_session=session)
        league_mapping = LeagueMapper.get_mapping(db_session=session)


    redis_instance.store_data("stat_mapper", static_mapping)
    redis_instance.store_data("league_mapper", league_mapping)

if __name__ == "__main__":
    store_static()








