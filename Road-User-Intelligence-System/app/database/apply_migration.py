"""
Migration script to add user_id column to tables and enable Supabase RLS.
"""

import os
import sqlite3
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=DOTENV_PATH, override=True)

logging.basicConfig(level=logging.INFO)


def migrate_sqlite():
    sqlite_path = os.path.join(BASE_DIR, "safety_events.db")
    if not os.path.exists(sqlite_path):
        logging.info(f"SQLite DB not found at {sqlite_path}, skipping SQLite migration.")
        return

    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    tables = ["vehicles", "violations", "session_summary", "rszsis_sync_queue"]
    for table in tables:
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cur.fetchone():
            continue
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        if "user_id" not in cols:
            logging.info(f"[SQLite] Adding user_id column to {table}")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")

    conn.commit()
    conn.close()
    logging.info("[SQLite] Migration complete.")


def migrate_postgres():
    db_uri = os.environ.get("DATABASE_URI")
    if not db_uri or not db_uri.startswith("postgres"):
        logging.info("No PostgreSQL DATABASE_URI configured, skipping Postgres migration.")
        return

    logging.info("[PostgreSQL] Applying migrations & RLS policies...")
    engine = create_engine(db_uri)
    with engine.begin() as conn:
        tables = ["vehicles", "violations", "session_summary"]
        for table in tables:
            # Add user_id column if missing
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR;"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table} (user_id);"))
            
            # Enable Row Level Security (RLS)
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))

            # Drop legacy permissive policies if present
            legacy_policies = [
                f"Authenticated users can read {table}",
                f"Enable read access for all users",
                f"Allow read for all users",
                f"public_read_{table}",
            ]
            for lpol in legacy_policies:
                conn.execute(text(f'DROP POLICY IF EXISTS "{lpol}" ON {table};'))

            # Create RLS policies for authenticated users
            # Drop existing policy first to be idempotent
            policies = [
                (f"user_select_{table}", f"CREATE POLICY user_select_{table} ON {table} FOR SELECT USING (auth.uid()::text = user_id);"),
                (f"user_insert_{table}", f"CREATE POLICY user_insert_{table} ON {table} FOR INSERT WITH CHECK (auth.uid()::text = user_id);"),
                (f"user_update_{table}", f"CREATE POLICY user_update_{table} ON {table} FOR UPDATE USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id);"),
                (f"user_delete_{table}", f"CREATE POLICY user_delete_{table} ON {table} FOR DELETE USING (auth.uid()::text = user_id);"),
            ]
            for pname, psql in policies:
                conn.execute(text(f"DROP POLICY IF EXISTS {pname} ON {table};"))
                try:
                    conn.execute(text(psql))
                except Exception as e:
                    logging.warning(f"Could not create policy {pname}: {e}")

    logging.info("[PostgreSQL] Migration complete.")


def main():
    migrate_sqlite()
    migrate_postgres()


if __name__ == "__main__":
    main()
