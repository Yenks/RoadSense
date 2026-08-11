"""
Central configuration for the School Zone Safety Intelligence System.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = BASE_DIR / ".env"

if "DATABASE_URI" in os.environ:
    logging.warning(
        "DATABASE_URI already set in OS environment before load_dotenv; .env will override it."
    )

load_dotenv(dotenv_path=DOTENV_PATH, override=True)

if not DOTENV_PATH.exists():
    logging.warning(f"Expected .env not found at {DOTENV_PATH}")

DATABASE_URI = os.environ["DATABASE_URI"]
SECRET_KEY = os.environ["SECRET_KEY"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")
RAW_VIDEOS_DIR = os.path.join(DATA_DIR, "raw_videos")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
CALIBRATION_DIR = os.path.join(DATA_DIR, "calibration")

# --- Detection ---
CONFIDENCE_THRESHOLD = 0.35
IOU_THRESHOLD = 0.5

# Model: yolov8m trained on VisDrone (aerial/drone imagery)
HF_REPO_ID = "mshamrai/yolov8m-visdrone"
HF_WEIGHTS_FILENAME = "best.pt"
LOCAL_MODEL_FILENAME = "yolov8m_visdrone.pt"

# VisDrone's native class map (index -> label)
VEHICLE_CLASSES = {
    2: "bicycle",
    3: "car",
    4: "van",
    5: "truck",
    6: "tricycle",
    7: "awning-tricycle",
    8: "bus",
    9: "motor",
}
PEDESTRIAN_CLASS = {0: "pedestrian", 1: "people"}

# Labels considered "rideable" for the rider-pairing check
RIDEABLE_LABELS = {"bicycle", "motor", "tricycle", "awning-tricycle"}
RIDER_OVERLAP_THRESHOLD = 0.25

# --- Detection Stabilization (Week 3 — used only by app/detection/detector.py) ---
STABILIZER_IOU_THRESHOLD = 0.3
STABILIZER_MIN_HITS_TO_CONFIRM = 1
STABILIZER_MAX_MISSED_FRAMES = 5
STABILIZER_SMOOTHING_ALPHA = 0.85
STABILIZER_USE_VELOCITY_PREDICTION = True

# --- Tracking (Week 4) ---
TRACK_ACTIVATION_THRESHOLD = 0.25
LOST_TRACK_BUFFER = 30
MINIMUM_MATCHING_THRESHOLD = 0.8

# --- Vehicle Counting (Week 4) ---
TRACK_CONFIRM_HITS_FOR_COUNT = 2

# --- Box Smoothing (Week 5 — applied on top of ByteTrack's tracked boxes) ---
BOX_SMOOTHING_ALPHA = 0.45

# --- Ground point for speed calc ---
# "center": box center — better for near-nadir (straight-down) drone views.
# "bottom": box bottom-edge — better for oblique/ground-level cameras.
GROUND_POINT_MODE = "center"

# --- Speed Estimation (Week 5) ---
SPEED_HISTORY_SECONDS = 2.0
MIN_TRACK_POINTS_FOR_SPEED = 5
SPEED_SMOOTHING_ALPHA = 0.15
SPEED_UPDATE_INTERVAL_FRAMES = 10
SPEED_OUTLIER_TRIM_FRACTION = 0.2
SPEED_USE_REGRESSION = True

# --- Display ---
SHOW_LABEL_WITH_SPEED = False  # False = show only speed, no vehicle type/ID

# --- Safety / Violations (used starting Week 6) ---
SPEED_LIMIT_KMH = 30.0  # Ghana Road Traffic Regulations 2012, L.I. 2180 — legal school-zone limit
CROSSING_ZONE_POLYGON = [
    (200, 400), (900, 400), (900, 500), (200, 500)
]
CONFLICT_DISTANCE_METERS = 3.0

# --- Database (used starting Week 8) ---
# NOTE: DATABASE_URI is set once from .env near the top of this file — do not reassign here.
DATABASE_PATH = os.path.join(BASE_DIR, "safety_events.db")

# --- Dashboard / Flask (used starting Week 8-9) ---
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# --- Enhanced calibration (Week 5, v2) ---
CALIBRATION_MIN_POINTS = 8  # was 4 — spread across near/far/left/right of frame

# --- Kalman + optical flow fusion ---
KALMAN_PROCESS_NOISE = 1e-2
KALMAN_MEASUREMENT_NOISE = 1e-1
ENABLE_OPTICAL_FLOW_CHECK = True
OPTICAL_FLOW_DISAGREEMENT_PX_THRESHOLD = 15.0  # if flow disagrees with detection by this many px, distrust this frame's measurement

# --- Outlier rejection (physical plausibility bounds) ---
MAX_PLAUSIBLE_SPEED_KMH = 150.0
MIN_PLAUSIBLE_SPEED_KMH = 1.0   # below this, treated as stationary (0), not rejected
MIN_TRACK_LENGTH_FOR_SPEED = 10  # frames a track must exist before its speed is trusted

# --- Violation Detection (Week 6) ---
VIOLATIONS_DIR = os.path.join(DATA_DIR, "violations")
VIOLATION_SNAPSHOT_PADDING_PX = 20  # extra margin around the vehicle box in the saved snapshot
MIN_FRAMES_OVER_LIMIT_TO_FLAG = 5   # avoid flagging a single noisy frame as a violation

# --- Crossing / Yield Monitoring (Week 6-7 combined) ---
# Legal basis: Ghana Road Traffic Act 2004 (Act 683) — vehicles must stop
# for pedestrians attempting to cross; Road Traffic Regulations 2012
# (L.I. 2180) Sec 73(1) — failure to give precedence to a pedestrian on a
# zebra crossing is an offence. The 30m figure below is Act 683's defined
# no-overtaking distance near a crossing — reused here as the approach
# zone's size (a reasonable buffer choice), not a literal "reduced speed
# within 30m" legal rule, which does not exist; the actual legal
# requirement in that zone is to stop/yield, not merely slow down.
APPROACH_ZONE_EXTRA_METERS = 30.0
YIELD_SPEED_THRESHOLD_KMH = 8.0  # project-defined: above this while a pedestrian
                                  # is on/entering the crossing counts as failure to yield
PEDESTRIAN_CROSSING_BUFFER_METERS = 2.0  # counts a pedestrian as "at the crossing"
                                          # if within this distance of its edge, not just on it
# --- Database import filtering ---
MIN_VEHICLE_TRACK_DURATION_SEC = 1.0  # tracks shorter than this are likely
                                        # fragmented re-detections, not real vehicles

# --- Dashboard / Auth (Week 9) ---
# NOTE: SECRET_KEY is set once from .env near the top of this file — do not reassign here.

# --- Speed validity region (prevents homography extrapolation errors) ---
SPEED_VALID_REGION_BUFFER_METERS = 5.0  # margin around the calibrated zone where speed is still trusted