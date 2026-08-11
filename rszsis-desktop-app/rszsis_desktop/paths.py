from __future__ import annotations
import os
import sys
from pathlib import Path
APP_DIR = Path(__file__).resolve().parents[1]
RUIS_DIR = APP_DIR.parent
PIPELINE_DIR = RUIS_DIR / "Road-User-Intelligence-System"
ENV_PATH = APP_DIR / ".env"
def add_pipeline_to_path() -> Path:
    bundled = app_root() / "Road-User-Intelligence-System"
    pipeline = bundled if bundled.exists() else PIPELINE_DIR.resolve()
    if not pipeline.exists():
        raise FileNotFoundError(f"Existing pipeline project not found: {pipeline}")
    pipeline_str = str(pipeline)
    if pipeline_str not in sys.path:
        sys.path.insert(0, pipeline_str)
    return pipeline
def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return APP_DIR
def pipeline_data_dir() -> Path:
    bundled = app_root() / "Road-User-Intelligence-System" / "data"
    if bundled.exists():
        return bundled
    return PIPELINE_DIR / "data"
def load_pipeline_config():
    add_pipeline_to_path()
    from app import config
    return config
def calibration_path_for(video_path: str) -> Path:
    config = load_pipeline_config()
    base = Path(video_path).stem
    return Path(config.CALIBRATION_DIR) / f"{base}_calibration.json"
def ensure_packaged_runtime_paths() -> None:
    add_pipeline_to_path()
    from app import config
    root = app_root()
    packaged_project = root / "Road-User-Intelligence-System"
    if not packaged_project.exists():
        return
    base = packaged_project
    data = base / "data"
    config.BASE_DIR = str(base)
    config.DATA_DIR = str(data)
    config.MODELS_DIR = str(data / "models")
    config.RAW_VIDEOS_DIR = str(data / "raw_videos")
    config.PROCESSED_DIR = str(data / "processed")
    config.CALIBRATION_DIR = str(data / "calibration")
    config.VIOLATIONS_DIR = str(data / "violations")
    config.DATABASE_PATH = str(base / "safety_events.db")
    config.DATABASE_URI = f"sqlite:///{config.DATABASE_PATH}"