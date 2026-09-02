from sqlalchemy import DateTime, func
from sqlalchemy import select
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, Session
from Database.base_db import Base


class StatMapper(Base):
    __tablename__ = "stats_mapper"

    raw_name: Mapped[str] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column()
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.raw_name, cls.normalized_name)
        ).all()
        return {row.raw_name: row.normalized_name for row in rows}


class LeagueMapper(Base):
    __tablename__ = "league_mapper"

    raw_name: Mapped[str] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column()
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.raw_name, cls.normalized_name)
        ).all()
        return {row.raw_name: row.normalized_name for row in rows}

# if __name__ == "__main__":
#     from Database.base_db import sync_engine
#     engine = sync_engine()
#     Base.metadata.create_all(engine)
#     from sqlalchemy.orm import sessionmaker
#     from sqlalchemy import insert
#
#     Session = sessionmaker(bind=engine)
#
#     import json
#     with open("league_mapper.json", "r") as file:
#         data = json.load(file)
#
#     new_data = [
#         {
#             "raw_name": d.get("raw_name"),
#             "normalized_name": d.get("normalized_name"),
#         }
#         for d in data.get("league_mapper")
#     ]
#
#
#
#
#
#     with Session() as session:
#         session.execute(insert(LeagueMapper).values(new_data))
#         session.commit()

