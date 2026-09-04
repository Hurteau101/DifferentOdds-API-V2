from sqlalchemy import DateTime, func, UniqueConstraint
from sqlalchemy import select
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, Session
from Database.base_db import Base
from sqlalchemy.dialects.postgresql import insert


class VerifiedStats(Base):
    __tablename__ = "verified_stats"

    received_name: Mapped[str] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column()
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.received_name, cls.normalized_name)
        ).all()
        return {row.received_name: row.normalized_name for row in rows}



class VerifiedLeague(Base):
    __tablename__ = "verified_league"

    received_name: Mapped[str] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column()
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.received_name, cls.normalized_name)
        ).all()
        return {row.received_name: row.normalized_name for row in rows}

class VerifiedTeams(Base):
    __tablename__ = "verified_team"
    __table_args__ = (
        UniqueConstraint("received_name", "league", name="unique_received_name_league_verified"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    received_name: Mapped[str] = mapped_column()
    normalized_name: Mapped[str] = mapped_column()
    abbreviation: Mapped[str | None] = mapped_column()
    league: Mapped[str] = mapped_column()
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def update_mapping(cls, db_session: Session, team_mapping: list):
        valid = cls.__table__.columns.keys()
        invalid = {key for mapping in team_mapping for key in mapping if key not in valid}

        if invalid:
            raise KeyError(f"Invalid keys {sorted(invalid)} - Valid Keys: {list(valid)}")

        stmt = insert(cls).values(team_mapping)
        stmt = stmt.on_conflict_do_nothing(index_elements=["received_name", "league"]).returning(cls)
        db_session.execute(stmt)
        db_session.commit()



    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.received_name, cls.normalized_name, cls.abbreviation, cls.league)
        ).all()
        return {
            row.received_name: {
                "normalized_name": row.normalized_name,
                "abbreviation": row.abbreviation,
                "league": row.league,
            }
            for row in rows
        }


class VerificationTeam(Base):
    __tablename__ = "verification_team"
    __table_args__ = (
        UniqueConstraint("received_name", "original_league", name="unique_received_name_league_verification"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    received_name: Mapped[str] = mapped_column()
    normalized_name: Mapped[str | None] = mapped_column()
    abbreviation: Mapped[str | None] = mapped_column()
    league: Mapped[str | None] = mapped_column()
    source: Mapped[str] = mapped_column()
    sportsbook: Mapped[str] = mapped_column()
    original_league: Mapped[str] = mapped_column()
    error_message: Mapped[str | None] = mapped_column()
    verified_successfully: Mapped[bool] = mapped_column(default=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def update_mapping(cls, db_session: Session, team_mapping: list):
        bulk_insert_into_verification_table(
            class_instance=cls,
            mapping_data=team_mapping,
            db_session=db_session,
            index_elements=["received_name", "original_league"]
        )

    @classmethod
    def get_mapping(cls, db_session: Session):
        """Get the mapping values as raw key name as the key and the normalized name as the value"""
        rows = db_session.execute(
            select(cls.received_name, cls.original_league)
        ).all()

        return [(row.received_name, row.original_league) for row in rows]


class VerificationLeague(Base):
    __tablename__ = "verification_league"
    id: Mapped[int] = mapped_column(primary_key=True)
    received_name: Mapped[str] = mapped_column(unique=True)
    normalized_name: Mapped[str | None] = mapped_column()
    sportsbook: Mapped[str] = mapped_column()
    verified_successfully: Mapped[bool] = mapped_column(default=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def update_mapping(cls, db_session: Session, league_mapping: list):
        bulk_insert_into_verification_table(
            class_instance=cls,
            mapping_data=league_mapping,
            db_session=db_session,
            index_elements=["received_name"]
        )


class VerificationStats(Base):
    __tablename__ = "verification_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    received_name: Mapped[str] = mapped_column(unique=True)
    sportsbook: Mapped[str] = mapped_column()
    normalized_name: Mapped[str | None] = mapped_column()
    verified_successfully: Mapped[bool] = mapped_column(default=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def update_mapping(cls, db_session: Session, stat_mapping: list):
        bulk_insert_into_verification_table(
            class_instance=cls,
            mapping_data=stat_mapping,
            db_session=db_session,
            index_elements=["received_name"]
        )

def bulk_insert_into_verification_table(
        class_instance: type[VerificationTeam, VerificationStats, VerificationLeague],
        mapping_data: list,
        db_session: Session,
        index_elements: list
):
    """Bulk insert mapping data into a verification table"""
    valid = class_instance.__table__.columns.keys()
    invalid = {key for mapping in mapping_data for key in mapping if key not in valid}

    if invalid:
        raise KeyError(f"Invalid keys {sorted(invalid)} - Valid Keys: {list(valid)}")

    stmt = insert(class_instance).values(mapping_data)
    stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
    db_session.execute(stmt)
    db_session.commit()



if __name__ == "__main__":
    from Database.base_db import sync_engine
    engine = sync_engine()
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    # Session = sessionmaker(bind=engine)
    #
    # import json
    #
    # with open("stat_mapper.json", "r", encoding="UTF-8") as file:
    #     data = json.load(file)
    #
    # new_data = [
    #     {
    #         "raw_name": d.get("raw_name"),
    #         "normalized_name": d.get("normalized_name"),
    #         "created_date": d.get("created_date")
    #     }
    #     for d in data.get("stats_mapper")
    # ]
    #
    # with Session() as session:
    #     session.execute(insert(VerifiedStats).values(new_data))
    #     session.commit()

