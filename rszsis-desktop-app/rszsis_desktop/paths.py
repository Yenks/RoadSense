from __future__ import annotations
import os
import sys
from pathlib import Path
APP_DIR = Path(__file__).resolve().parents[1]
RUIS_DIR = APP_DIR.parent
PIPELINE_DIR = RUIS_DIR / "Road-User-Intelligence-System"
ENV_PATH = APP_DIR / ".env"
def add_pipeline_to_path() -> Path:
    root = app_root()
    meipass = getattr(sys, "_MEIPASS", None)

    candidates = []
    if getattr(sys, "frozen", False):
        if meipass:
            candidates.append(Path(meipass) / "Road-User-Intelligence-System")
        candidates.append(root / "_internal" / "Road-User-Intelligence-System")
        candidates.append(root / "Road-User-Intelligence-System")
    candidates.append(PIPELINE_DIR.resolve())

    pipeline = None
    for cand in candidates:
        if cand.exists():
            pipeline = cand
            break

    if not pipeline:
        raise FileNotFoundError(f"Existing pipeline project not found in candidates: {candidates}")

    pipeline_str = str(pipeline)
    if pipeline_str not in sys.path:
        sys.path.insert(0, pipeline_str)
    return pipeline

def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return APP_DIR

def pipeline_data_dir() -> Path:
    pipeline = add_pipeline_to_path()
    return pipeline / "data"

def _ensure_env_placeholders() -> None:
    os.environ.setdefault("DATABASE_URI", "sqlite:///placeholder.db")
    os.environ.setdefault("SECRET_KEY", "desktop-default-secret-key")

def load_pipeline_config():
    add_pipeline_to_path()
    _ensure_env_placeholders()
    from app import config
    return config

def calibration_path_for(video_path: str) -> Path:
    config = load_pipeline_config()
    base = Path(video_path).stem
    return Path(config.CALIBRATION_DIR) / f"{base}_calibration.json"

def ensure_packaged_runtime_paths() -> None:
    _ensure_env_placeholders()
    pipeline = add_pipeline_to_path()
    from app import config
    root = app_root()

    base = pipeline
    data = base / "data"

    output_data_dir = root / "Road-User-Intelligence-System" / "data"
    output_data_dir.mkdir(parents=True, exist_ok=True)
    for folder in ["raw_videos", "processed", "violations", "calibration_frames"]:
        (output_data_dir / folder).mkdir(parents=True, exist_ok=True)

    config.BASE_DIR = str(base)
    config.DATA_DIR = str(data)
    config.MODELS_DIR = str(data / "models")
    config.RAW_VIDEOS_DIR = str(output_data_dir / "raw_videos")
    config.PROCESSED_DIR = str(output_data_dir / "processed")
    config.CALIBRATION_DIR = str(data / "calibration")
    config.VIOLATIONS_DIR = str(output_data_dir / "violations")
    config.DATABASE_PATH = str(base / "safety_events.db")
    config.DATABASE_URI = f"sqlite:///{config.DATABASE_PATH}"