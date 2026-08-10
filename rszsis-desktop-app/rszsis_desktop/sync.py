from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

from .paths import ENV_PATH, add_pipeline_to_path

log = logging.getLogger(__name__)


class SyncManager:
    def __init__(self):
        add_pipeline_to_path()
        from app.config import DATABASE_PATH
        self.db_path = Path(DATABASE_PATH)
        self._client = None
        self.ensure_queue()

    def connect(self):
        """Return a service_role Supabase client used only for data sync writes.

        This is intentionally separate from AuthManager's anon-key client.
        """
        if self._client is not None:
            return self._client
        load_dotenv(ENV_PATH)
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required in .env")
        from supabase import create_client
        self._client = create_client(url, key)
        return self._client

    def ensure_queue(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists rszsis_sync_queue (
                    id integer primary key autoincrement,
                    video_name text not null unique,
                    status text not null default 'pending',
                    attempts integer not null default 0,
                    last_error text,
                    updated_at text not null
                )
                """
            )
            conn.commit()

    def mark_pending(self, video_name: str, error: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into rszsis_sync_queue(video_name, status, attempts, last_error, updated_at)
                values (?, 'pending', 0, ?, ?)
                on conflict(video_name) do update set
                    status = 'pending',
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (video_name, error, now),
            )
            conn.commit()

    def mark_synced(self, video_name: str) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into rszsis_sync_queue(video_name, status, attempts, last_error, updated_at)
                values (?, 'synced', 0, null, ?)
                on conflict(video_name) do update set
                    status = 'synced',
                    last_error = null,
                    updated_at = excluded.updated_at
                """,
                (video_name, now),
            )
            conn.commit()

    def pending_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("select count(*) from rszsis_sync_queue where status != 'synced'").fetchone()
        return int(row[0] if row else 0)

    def pending_videos(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("select video_name from rszsis_sync_queue where status != 'synced' order by updated_at").fetchall()
        return [row[0] for row in rows]

    def retry_pending(self) -> tuple[int, int]:
        ok = 0
        failed = 0
        for video_name in self.pending_videos():
            if self.sync_video(video_name):
                ok += 1
            else:
                failed += 1
        return ok, failed

    def sync_video(self, video_name: str) -> bool:
        try:
            payloads = self._payloads(video_name)
            client = self.connect()
            for table in ("violations", "vehicles", "session_summary"):
                client.table(table).delete().eq("video_name", video_name).execute()
            for table in ("vehicles", "violations", "session_summary"):
                rows = payloads[table]
                if rows:
                    client.table(table).insert(rows).execute()
            self.mark_synced(video_name)
            return True
        except Exception as exc:  # network/API failures must not break local work
            log.exception("Supabase sync failed for %s", video_name)
            self._record_failure(video_name, str(exc))
            return False

    def _record_failure(self, video_name: str, error: str) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into rszsis_sync_queue(video_name, status, attempts, last_error, updated_at)
                values (?, 'pending', 1, ?, ?)
                on conflict(video_name) do update set
                    status = 'pending',
                    attempts = attempts + 1,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (video_name, error[:1000], now),
            )
            conn.commit()

    def _payloads(self, video_name: str) -> dict[str, list[dict]]:
        add_pipeline_to_path()
        from app.database.db import get_session, init_db
        from app.database.models import SessionSummary, Vehicle, Violation

        init_db()
        session = get_session()
        try:
            vehicles = session.query(Vehicle).filter(Vehicle.video_name == video_name).all()
            violations = session.query(Violation).filter(Violation.video_name == video_name).all()
            summaries = session.query(SessionSummary).filter(SessionSummary.video_name == video_name).all()
            return {
                "vehicles": [self._row(v, ["video_name", "track_id", "vehicle_class", "is_rider", "entry_time_sec", "exit_time_sec", "max_speed_kmh", "avg_speed_kmh"]) for v in vehicles],
                "violations": [self._row(v, ["video_name", "track_id", "vehicle_class", "violation_type", "timestamp_sec", "speed_kmh", "threshold_kmh", "snapshot_path"]) for v in violations],
                "session_summary": [self._row(s, ["video_name", "duration_sec", "total_vehicles", "avg_speed_kmh", "peak_speed_kmh", "total_violations", "processed_at"]) for s in summaries],
            }
        finally:
            session.close()

    @staticmethod
    def _row(obj, fields: Iterable[str]) -> dict:
        row = {}
        for field in fields:
            value = getattr(obj, field)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            row[field] = value
        return row
