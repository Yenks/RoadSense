"""
Database connection setup — Week 8.
"""

import logging
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URI
from app.database.models import Base


def _debug_database_uri(uri: str):
    parsed = urlparse(uri)
    username = parsed.username
    hostname = parsed.hostname
    port = parsed.port or 5432
    dbname = parsed.path.lstrip("/")
    msg = (
        f"[DB DEBUG] DATABASE_URI parsed: user={username!r} host={hostname!r} "
        f"port={port!r} dbname={dbname!r}"
    )
    logging.debug(msg)
    print(msg)
    return parsed

_debug_database_uri(DATABASE_URI)

engine = create_engine(DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Creates all tables if they don't already exist. Safe to call every run."""
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()