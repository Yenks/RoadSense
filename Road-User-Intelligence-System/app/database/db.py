"""
Database connection setup — Week 8.
"""

import logging
import time
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
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

# pool_pre_ping checks each pooled connection with a lightweight query before
# handing it out, so a stale/dropped connection is transparently replaced
# instead of surfacing as an error on the next request.
engine = create_engine(DATABASE_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db(retries: int = 3, delay: float = 2.0):
    """
    Creates all tables if they don't already exist. Safe to call every run.

    Retries on OperationalError (e.g. transient DNS resolution failures —
    "could not translate host name to address") since these have been
    observed to be intermittent on some networks rather than a persistent
    misconfiguration.
    """
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(engine)
            return
        except OperationalError as e:
            if attempt == retries:
                logging.error(
                    f"[DB] init_db failed after {retries} attempts: {e}"
                )
                raise
            logging.warning(
                f"[DB] init_db attempt {attempt}/{retries} failed "
                f"({e.__class__.__name__}); retrying in {delay}s..."
            )
            print(
                f"[DB] Connection attempt {attempt}/{retries} failed, "
                f"retrying in {delay}s..."
            )
            time.sleep(delay)


def get_session():
    return SessionLocal()