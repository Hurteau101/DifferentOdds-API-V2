from typing import List
from sqlalchemy import ARRAY, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import ForeignKey, UniqueConstraint, Index, select
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload, sessionmaker, Session, validates
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from Database.base_db import Base, to_dict
import sqlalchemy.types as types

class EmptyArg(types.TypeDecorator):
    impl = types.Float
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value == '':
            return None

        return value


class AutoSGPConfigs(Base):
    __tablename__ = "autosgp_config"

    unique_name: Mapped[str] = mapped_column(primary_key=True)
    league_name: Mapped[str] = mapped_column(ForeignKey("auto_sgp_league.league_name", ondelete="CASCADE"))
    league: Mapped["AutoSGPLeagues"] = relationship(back_populates="configs")
    stat_types: Mapped[List[str]] = mapped_column(ARRAY(String))
    discord_min_ev: Mapped[float] = mapped_column()
    max_uses: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(default=True)

    @classmethod
    def get_active_configs(cls, session: Session):
        rows = session.scalars(
            select(cls).where(cls.is_active)
        )

        return [to_dict(row) for row in rows]


class AutoSGPLeagues(Base):
    __tablename__ = "auto_sgp_league"

    league_name: Mapped[str] = mapped_column(primary_key=True)
    configs: Mapped[list["AutoSGPConfigs"]] = relationship(back_populates="league")

class SGPHistory(Base):
    __tablename__ = "sgp_history"

    game_key: Mapped[str] = mapped_column(primary_key=True)
    leg: Mapped[List["SGPLeg"]] = relationship(back_populates="leg_history", cascade="all, delete-orphan", passive_deletes=True)
    sgp_book: Mapped[List["SGPBook"]] = relationship(back_populates="book_history", cascade="all, delete-orphan", passive_deletes=True)
    extra_info: Mapped[List["SGPExtraInfo"]] = relationship(back_populates="extra_history", cascade="all, delete-orphan", passive_deletes=True)

    @staticmethod
    def _organize_history(rows: list):
        snapshots = defaultdict(lambda: defaultdict(lambda: {"legs": [], "books": [], "extra_info": []}))

        for row in rows:
            game_key = row["game_key"]

            for leg in row["legs"]:
                snapshots[game_key][leg["timestamp"]]["legs"].append(leg)

            for book in row["books"]:
                snapshots[game_key][book["timestamp"]]["books"].append(book)

            for extra in row["extra_info"]:
                snapshots[game_key][extra["timestamp"]]["extra_info"].append(extra)

        return {
            key: dict(value)
            for key,value in snapshots.items()
        }

    @classmethod
    async def all_history(cls, session: AsyncSession):
        result = await session.execute(
            select(cls).options(
                selectinload(cls.leg),
                selectinload(cls.sgp_book),
                selectinload(cls.extra_info),
            )
        )

        rows = result.scalars().all()

        row_list = [
            {
                "game_key": row.game_key,
                "legs": [to_dict(l) for l in row.leg],
                "books": [to_dict(b) for b in row.sgp_book],
                "extra_info": [to_dict(e) for e in row.extra_info],
            }
            for row in rows
        ]

        return cls._organize_history(rows=row_list)


class SGPLeg(Base):
    __tablename__ = "sgp_history_leg"
    __table_args__ = (
        UniqueConstraint("game_key", "timestamp", "normalized_name", name="leg_unique_time_name_game_key"),
        Index("leg_inx_time_game_key", "timestamp" ,"game_key")
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    game_key: Mapped[str] = mapped_column(ForeignKey("sgp_history.game_key", ondelete="CASCADE"))
    leg_history: Mapped["SGPHistory"] = relationship(back_populates="leg")
    event_name: Mapped[str] = mapped_column()
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_league: Mapped[str] = mapped_column()
    individual_odds: Mapped[dict | None] = mapped_column(JSONB)
    leg_number: Mapped[int] = mapped_column()
    normalized_name: Mapped[str] = mapped_column()
    market_type: Mapped[str] = mapped_column()
    line: Mapped[float | None] = mapped_column(EmptyArg)
    team: Mapped[str | None] = mapped_column()
    player_name: Mapped[str | None] = mapped_column()
    nvig: Mapped[float] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        fields = [
            self.market_type,
            self.line,
            self.team,
            self.player_name,
            self.nvig,
            self.timestamp
        ]

        return " ".join(str(db_field) for db_field in fields if db_field is not None)


class SGPBook(Base):
    __tablename__ = "sgp_history_book"
    __table_args__ = (
        UniqueConstraint("game_key", "timestamp", "book_name", name="book_unique_time_book_name_game_key"),
        Index("book_inx_time_game_key", "timestamp" ,"game_key")
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    game_key: Mapped[str] = mapped_column(ForeignKey("sgp_history.game_key", ondelete="CASCADE"))
    book_history: Mapped["SGPHistory"] = relationship(back_populates="sgp_book")
    book_name: Mapped[str] = mapped_column()
    sgp_odd: Mapped[float | None] = mapped_column()
    median_met: Mapped[bool] = mapped_column()
    ev: Mapped[float | None] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"{self.book_name} {self.sgp_odd}"

class SGPExtraInfo(Base):
    __tablename__ = "sgp_extract_info_history"
    __table_args__ = (
        UniqueConstraint("game_key", "timestamp", name="extra_unique_time_game_key"),
        Index("extra_inx_time_game_key", "timestamp" ,"game_key")
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    game_key: Mapped[str] = mapped_column(ForeignKey("sgp_history.game_key", ondelete="CASCADE"))
    extra_history: Mapped["SGPHistory"] = relationship(back_populates="extra_info")
    non_correlated_price: Mapped[float] = mapped_column()
    weighted_fair_value: Mapped[float] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"{self.game_key}"

if __name__ == "__main__":
    from Database.base_db import sync_engine
    engine = sync_engine()
    Base.metadata.create_all(engine)

    # Session = sessionmaker(engine)
    # leagues = [{"league_name": "WNBA"}, {"league_name": "MLB"}, {"league_name": "NFL"}, {"league_name": "NBA"},
    #            {"league_name": "NCAAB"}, {"league_name": "NCAAF"}]
    #
    # # unique_name: Mapped[str] = mapped_column(primary_key=True)
    # # league_name: Mapped[str] = mapped_column(ForeignKey("auto_sgp_league.league_name", ondelete="CASCADE"))
    # # league: Mapped["AutoSGPLeagues"] = relationship(back_populates="configs")
    # # stat_types: Mapped[List[str]] = mapped_column(ARRAY(String))
    # # multiple_teams: Mapped[bool] = mapped_column(default=False)
    # # discord_min_ev: Mapped[float] = mapped_column(nullable=False)
    # # endpoint_min_ev: Mapped[float] = mapped_column(nullable=False)
    # # is_active: Mapped[bool] = mapped_column(default=True)
    # #
    # configs = [
    #     {"unique_name": "mlb-player-rbi-bases", "league_name": "MLB", "stat_types": ["Player Hits + Runs + RBIs", "Player Bases"], "multiple_teams": False, "discord_min_ev": 15.0, "endpoint_min_ev": 0.0, "is_active": False},
    #     {"unique_name": "ncaaf-moneyline-total-points", "league_name": "NCAAF",
    #      "stat_types": ["Total Points","Moneyline"], "multiple_teams": False, "discord_min_ev": 15.0,
    #      "endpoint_min_ev": 0.0, "is_active": False},
    #     {"unique_name": "wnba-rebounds-pra", "league_name": "WNBA",
    #      "stat_types": ["Player Rebounds","Player Points + Rebounds"], "multiple_teams": False, "discord_min_ev": 15.0,
    #      "endpoint_min_ev": 0.0, "is_active": False},
    #     {"unique_name": "mlb-runline-hits-allowed", "league_name": "MLB",
    #      "stat_types": ["Run Line","Player Hits Allowed"], "multiple_teams": False, "discord_min_ev": 15.0,
    #      "endpoint_min_ev": 0.0, "is_active": False},
    #     {"unique_name": "wnba-rebounds-pra-rebounds", "league_name": "WNBA",
    #      "stat_types": ["Player Rebounds","Player Points + Rebounds","Player Rebounds"], "multiple_teams": True, "discord_min_ev": 15.0,
    #      "endpoint_min_ev": 0.0, "is_active": True}
    # ]
    #
    # with Session.begin() as session:
    #     # rows = AutoSGPConfigs.get_active_configs(session=session)
    #     # print(rows)
    #     session.execute(insert(AutoSGPLeagues).values(leagues))
    #     session.execute(insert(AutoSGPConfigs).values(configs))
        #
        # league = AutoSGPLeagues(league_name="test")
        # session.add(league)
        # session.commit()
