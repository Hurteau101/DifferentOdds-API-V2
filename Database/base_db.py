from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy.engine import URL, create_engine
import os
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from functools import lru_cache
from typing import Annotated, AsyncGenerator
from Utils.helpers import is_production

load_dotenv()

def _url(production: bool, driver: str):
    return URL.create(
        driver,
        username=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        database=os.getenv('DB_NAME') if production else os.getenv('DB_NAME_TEST'),
    )

# Cache to only create one.
@lru_cache(maxsize=1)
def async_engine():
    production = is_production()
    return create_async_engine(
        _url(production, "postgresql+asyncpg"),
        echo=not production,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )

# Cache to only create one.
@lru_cache(maxsize=1)
def async_session_maker():
    return async_sessionmaker(async_engine(), expire_on_commit=False)


@lru_cache(maxsize=1)
def sync_engine():
    production = is_production()
    return create_engine(
        _url(production, "postgresql"),
        echo=not production,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )


def to_dict(obj):
    return {
        c.name: (getattr(obj, c.name).replace(tzinfo=timezone.utc) if isinstance(getattr(obj, c.name),
                                                                                 datetime) else getattr(obj, c.name))
        for c in obj.__table__.columns
    }

def new_async_session() -> AsyncSession:
    return async_session_maker()()

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with new_async_session() as session:
        yield session

DB = Annotated[AsyncSession, Depends(get_async_session)]

Base = declarative_base()

