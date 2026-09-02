import os
from cryptography.fernet import Fernet
from sqlalchemy import DateTime, func, select
from sqlalchemy import UniqueConstraint
from datetime import datetime

from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker, Session
from Database.base_db import Base


from dotenv import load_dotenv
load_dotenv()

fernet_key:str = os.getenv("FERNET_KEY")
if not fernet_key:
    raise ValueError("FERNET_KEY environment variable is not set.")

class EncryptType(TypeDecorator):
    impl = Text
    cache_ok = True
    
    def __init__(self, encryption_key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption_key = encryption_key
        self.fernet = Fernet(fernet_key.encode())

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = self.fernet.encrypt(value.encode()).decode()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = self.fernet.decrypt(value.encode()).decode()
        return value


class APIKeys(Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("client", name="unique_client"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client: Mapped[str] = mapped_column()
    api_key: Mapped[str] = mapped_column(EncryptType(encryption_key=fernet_key))
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    @classmethod
    def get_api_keys(cls, db_session: Session):
        rows = db_session.execute(
            select(cls.client, cls.api_key)
        ).all()
        return {row.client: row.api_key for row in rows}


if __name__ == "__main__":
    from Database.base_db import sync_engine
    engine = sync_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)

    with Session.begin() as session:
        test = APIKeys.get_api_keys(session)
        

        # api_key = APIKeys(
        #     client="Test",
        #     api_key="DiaNpT0g7VhhQPU1ZH7vf5b1hb6J1SGk"
        # )
        #
        # session.add(api_key)




