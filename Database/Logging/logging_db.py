from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column
from Database.base_db import Base
from datetime import date
from sqlalchemy import Date, DateTime, func, UniqueConstraint, Index, select
from sqlalchemy.orm import Session

class LoggingDetails(Base):
    __tablename__ = "book_logging_details"
    __table_args__ = (
        UniqueConstraint("book", "error_type", "day", name="unique_book_error_type_day"),
        Index("book_index", "book"),
    )

    log_id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, default=date.today)
    book: Mapped[str] = mapped_column()
    error_type: Mapped[str] = mapped_column()
    message: Mapped[str] = mapped_column()
    count: Mapped[int] = mapped_column(default=1, autoincrement=True)
    last_sent: Mapped[date] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    last_occurrence: Mapped[date] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @classmethod
    def update_last_sent(cls, db_session: Session, log_id: int):
        db_session.query(LoggingDetails).filter(LoggingDetails.log_id == log_id).update({
            "last_sent": func.now()
        })

        db_session.commit()

    @classmethod
    def update_error(cls, db_session: Session, details: dict):
        if not all([details.get(key) for key in ["book", "error_type", "message"]]):
            passed_in_keys = set(details.keys())
            required_keys = {"book", "error_type", "message"}
            raise ValueError(f"Missing required keys in details - [${passed_in_keys - required_keys}]")

        insert_smt = insert(LoggingDetails).values(details)
        do_update = insert_smt.on_conflict_do_update(
            index_elements=["book", "error_type", "day"],
            set_=dict(count=LoggingDetails.count + 1, last_occurrence=func.now())
        ).returning(LoggingDetails)

        orm_smt = select(LoggingDetails).from_statement(do_update)
        result = db_session.scalars(orm_smt).first()
        db_session.commit()
        return result




if __name__ == "__main__":
    from Database.base_db import sync_engine
    engine = sync_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        test = LoggingDetails.update_error(session, {"book": "Underdog", "error_type": "Authentication Error", "message": "Error"})
        log_id = test.log_id
        LoggingDetails.update_last_sent(session, log_id)

        # log = LoggingDetails(
        #     book="Underdog",
        #     error_type="Authentication Error",
        #     message="Error",
        # )
        # session.add(log)
        # session.commit()

        # details = {
        #     "book": "Underdog",
        #     "error_type": "Authentication Error",
        #     "message": "Error"
        # }
        #
        # insert_smt = insert(LoggingDetails).values(details)
        # do_update = insert_smt.on_conflict_do_update(
        #     index_elements=["book", "error_type", "day"],
        #     set_=dict(count=insert_smt.excluded.count + 1, last_occurrence=func.now())
        # )
        #
        # session.execute(do_update)
        # session.commit()

