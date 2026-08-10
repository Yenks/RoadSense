"""
End-to-end verification script for RSZSIS Desktop App.

1. Tests AuthManager client creation with SUPABASE_ANON_KEY.
2. Tests processing pipeline on raw video DJI_0521_720p.mp4.
3. Tests DB importer and local SQLite storage in safety_events.db.
4. Tests SyncManager one-way cloud sync to Supabase.
"""

import os
import sys
from pathlib import Path

# Ensure paths
APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from rszsis_desktop.auth import AuthManager
from rszsis_desktop.paths import add_pipeline_to_path, ensure_packaged_runtime_paths, PIPELINE_DIR
from rszsis_desktop.sync import SyncManager

print("--- 1. Testing AuthManager (Anon Key Client) ---")
auth = AuthManager()
client = auth.connect()
print(f"AuthManager client initialized cleanly. Base URL: {auth._client.supabase_url}")

print("\n--- 2. Testing Processing Pipeline ---")
ensure_packaged_runtime_paths()
add_pipeline_to_path()

video_path = str(PIPELINE_DIR / "data" / "raw_videos" / "DJI_0521_720p.mp4")
calibration_path = str(PIPELINE_DIR / "data" / "calibration" / "DJI_0521_720p_calibration.json")

print(f"Video path: {video_path}")
print(f"Calibration path: {calibration_path}")
assert os.path.exists(video_path), f"Missing video file: {video_path}"
assert os.path.exists(calibration_path), f"Missing calibration file: {calibration_path}"

from app.safety.pipeline import ViolationPipeline
from app.database.importer import import_video
from app.database.db import get_session, init_db
from app.database.models import SessionSummary, Vehicle, Violation

pipeline = ViolationPipeline(calibration_path)

frames_processed = [0]
def progress_cb(current, total):
    frames_processed[0] = current

print("Running ViolationPipeline on DJI_0521_720p.mp4...")
result = pipeline.run(
    video_path,
    show_preview=False,
    progress_callback=progress_cb,
)

print(f"Pipeline run complete! Processed {frames_processed[0]} frames.")
print(f"Result summary: {result}")

print("\n--- 3. Testing Local DB Importer ---")
video_name = Path(video_path).stem
import_video(video_name)
init_db()

session = get_session()
try:
    summary = session.query(SessionSummary).filter(SessionSummary.video_name == video_name).one_or_none()
    vehicles = session.query(Vehicle).filter(Vehicle.video_name == video_name).all()
    violations = session.query(Violation).filter(Violation.video_name == video_name).all()
    print(f"Local SQLite DB check:")
    print(f"  SessionSummary: {summary.total_vehicles} vehicles, {summary.total_violations} violations, peak speed {summary.peak_speed_kmh} km/h")
    print(f"  Vehicles count: {len(vehicles)}")
    print(f"  Violations count: {len(violations)}")
finally:
    session.close()

print("\n--- 4. Testing Supabase Cloud Sync ---")
sync = SyncManager()
sync.mark_pending(video_name)
success = sync.sync_video(video_name)
print(f"SyncManager result for {video_name}: {success}")

if success:
    sp_client = sync.connect()
    summary_cloud = sp_client.table("session_summary").select("*").eq("video_name", video_name).execute()
    vehicles_cloud = sp_client.table("vehicles").select("*").eq("video_name", video_name).execute()
    violations_cloud = sp_client.table("violations").select("*").eq("video_name", video_name).execute()
    print("Supabase Cloud Query Verification:")
    print(f"  Cloud session_summary rows: {len(summary_cloud.data)}")
    print(f"  Cloud vehicles rows: {len(vehicles_cloud.data)}")
    print(f"  Cloud violations rows: {len(violations_cloud.data)}")
    if len(summary_cloud.data) > 0:
        print(f"  Cloud summary data sample: {summary_cloud.data[0]}")
    print("\nE2E VERIFICATION SUCCESSFUL!")
else:
    print("\nE2E VERIFICATION FAILED AT SYNC STEP!")
