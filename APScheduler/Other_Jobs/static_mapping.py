"""Used to store static data into Redis Database"""
from sqlalchemy.orm import sessionmaker
from Database.base_db import sync_engine
from Redis.redis_manager import RedisSyncManager
from Database.Sportsbooks.sportsbook_db import VerifiedLeague, VerifiedTeams, VerifiedStats


def store_static_mapping():
    redis_instance = RedisSyncManager(database=7)
    engine = sync_engine()
    Session = sessionmaker(bind=engine)

    with Session() as session:
        static_mapping = VerifiedStats.get_mapping(db_session=session)
        league_mapping = VerifiedLeague.get_mapping(db_session=session)
        team_mapping = VerifiedTeams.get_mapping(db_session=session)


    redis_instance.store_data(key_name="stat_mapper", data_to_store=static_mapping, key_expiration=780)
    redis_instance.store_data(key_name="league_mapper", data_to_store=league_mapping, key_expiration=780)
    redis_instance.store_data(key_name="team_mapper", data_to_store=team_mapping, key_expiration=780)

if __name__ == "__main__":
    store_static_mapping()








