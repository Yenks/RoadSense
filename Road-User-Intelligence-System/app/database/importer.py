"""
Database importer — Week 8.

Reads the already-generated JSON logs from Weeks 4-6 and populates the
database. Works two ways:
  1. Called directly, pointed at any already-processed video's logs
     (import existing results without re-running anything).
  2. Called automatically at the end of app/safety/pipeline.py's run,
     so a fresh pipeline run populates the DB immediately.
"""

import argparse
import json
import os
import statistics
from collections import defaultdict

from app.config import PROCESSED_DIR
from app.database.db import get_session, init_db
from app.database.models import Vehicle, Violation, SessionSummary


def import_video(video_base_name: str, user_id: str = None):
    init_db()
    session = get_session()

    speed_log_path = os.path.join(PROCESSED_DIR, f"{video_base_name}_week5_speed.json")
    violations_log_path = os.path.join(PROCESSED_DIR, f"{video_base_name}_week6_violations.json")

    if not os.path.exists(speed_log_path):
        raise FileNotFoundError(
            f"Speed log not found: {speed_log_path}\n"
            f"Run app.speed.pipeline (or app.safety.pipeline) for this video first."
        )

    with open(speed_log_path) as f:
        detections = json.load(f)

    # --- Build one Vehicle row per track_id, aggregated from per-frame detections ---
    by_track = defaultdict(list)
    for d in detections:
        if d["track_class"] == "vehicle" and d.get("track_id", -1) >= 0:
            by_track[d["track_id"]].append(d)

    # Clear any existing rows for this video and user (re-import is idempotent)
    v_query = session.query(Vehicle).filter(Vehicle.video_name == video_base_name)
    vio_query = session.query(Violation).filter(Violation.video_name == video_base_name)
    s_query = session.query(SessionSummary).filter(SessionSummary.video_name == video_base_name)

    if user_id:
        v_query = v_query.filter(Vehicle.user_id == user_id)
        vio_query = vio_query.filter(Violation.user_id == user_id)
        s_query = s_query.filter(SessionSummary.user_id == user_id)

    v_query.delete(synchronize_session=False)
    vio_query.delete(synchronize_session=False)
    s_query.delete(synchronize_session=False)

    vehicle_avg_speeds = []
    vehicle_peak_speeds = []

    from app.config import MIN_VEHICLE_TRACK_DURATION_SEC

    skipped_fragments = 0

    for track_id, records in by_track.items():
        timestamps = [r["timestamp_sec"] for r in records]
        duration = max(timestamps) - min(timestamps)

        if duration < MIN_VEHICLE_TRACK_DURATION_SEC:
            skipped_fragments += 1
            continue  # likely a fragmented re-detection, not a real distinct vehicle

        speeds = [r["speed_kmh"] for r in records if r.get("speed_kmh") is not None]

        max_speed = max(speeds) if speeds else None
        avg_speed = round(statistics.mean(speeds), 1) if speeds else None

        if max_speed is not None:
            vehicle_peak_speeds.append(max_speed)
        if avg_speed is not None:
            vehicle_avg_speeds.append(avg_speed)

        session.add(Vehicle(
            user_id=user_id,
            video_name=video_base_name,
            track_id=track_id,
            vehicle_class=records[0]["label"],
            is_rider=int(any(r.get("is_rider") for r in records)),
            entry_time_sec=min(timestamps),
            exit_time_sec=max(timestamps),
            max_speed_kmh=max_speed,
            avg_speed_kmh=avg_speed,
        ))

    # --- Violations (optional file — may not exist if only speed pipeline was run) ---
    total_violations = 0
    if os.path.exists(violations_log_path):
        with open(violations_log_path) as f:
            violations = json.load(f)

        for v in violations:
            session.add(Violation(
                user_id=user_id,
                video_name=video_base_name,
                track_id=v["track_id"],
                vehicle_class=v["label"],
                violation_type=v.get("violation_type", "speeding"),
                timestamp_sec=v["timestamp_sec"],
                speed_kmh=v["peak_speed_kmh"],
                threshold_kmh=v["speed_limit_kmh"],
                snapshot_path=v.get("snapshot_path"),
            ))
            total_violations += 1

    # --- Session summary ---
    duration_sec = max((d["timestamp_sec"] for d in detections), default=0.0)
    session.add(SessionSummary(
        user_id=user_id,
        video_name=video_base_name,
        duration_sec=duration_sec,
        total_vehicles=len(by_track) - skipped_fragments,
        avg_speed_kmh=round(statistics.mean(vehicle_avg_speeds), 1) if vehicle_avg_speeds else None,
        peak_speed_kmh=max(vehicle_peak_speeds) if vehicle_peak_speeds else None,
        total_violations=total_violations,
    ))

    session.commit()
    session.close()

    print(f"[DB Import] '{video_base_name}': {len(by_track) - skipped_fragments} vehicles imported "
          f"({skipped_fragments} short fragments filtered out), {total_violations} violations imported.")


def main():
    parser = argparse.ArgumentParser(description="Import processed video logs into the database")
    parser.add_argument("--video", required=True, help="Base video name, e.g. DJI_0567_720p")
    args = parser.parse_args()
    import_video(args.video)


if __name__ == "__main__":
    main()