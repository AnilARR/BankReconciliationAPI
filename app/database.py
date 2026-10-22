"""SQLAlchemy engine/session setup. Works with SQL Server (mssql+pyodbc) and SQLite for local tests."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Share one in-memory database across threads (used by the test suite).
            kwargs["poolclass"] = StaticPool
    elif url.startswith("mssql+pyodbc"):
        # Batches parameter sets into a single round trip for bulk inserts.
        kwargs["fast_executemany"] = True
    return create_engine(url, **kwargs)


_settings = get_settings()
engine = build_engine(_settings.database_url, echo=_settings.sql_echo)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
