"""Database engine and session helpers."""

from __future__ import annotations

import logging
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger("xtav2.db")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def normalize_database_url(url: str) -> str:
    """Use psycopg v3 (psycopg[binary]); plain postgresql:// defaults to psycopg2."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def _patch_schema(engine: Engine) -> None:
    """Idempotent column adds for existing Postgres/SQLite volumes."""
    statements = [
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'posted'",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS receipt_path VARCHAR(512)",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64)",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS duplicate_of_id INTEGER",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS duplicate_dismissed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS bank_ref VARCHAR(128)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except (OperationalError, ProgrammingError, DBAPIError) as exc:
                # SQLite < 3.35 may lack IF NOT EXISTS for ADD COLUMN — ignore duplicate.
                logger.debug("Schema patch skipped/failed for %s: %s", stmt, exc)


def init_db() -> None:
    """Create tables if missing and patch new columns (idempotent for V1)."""
    from app import models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _patch_schema(engine)


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
