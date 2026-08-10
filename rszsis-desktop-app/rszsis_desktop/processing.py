from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .paths import add_pipeline_to_path, calibration_path_for, ensure_packaged_runtime_paths
from .sync import SyncManager


class ProcessingWorker(QThread):
    frame_ready = pyqtSignal(QImage)
    stats_ready = pyqtSignal(dict)
    progress_ready = pyqtSignal(int, int)
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, video_path: str, sensitivity_frames: int, retain_logs: bool = True, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.sensitivity_frames = sensitivity_frames
        # retain_logs is accepted for UI compatibility but currently unused:
        # JSON/CSV logs are always written (required by import_video / debugging).
        self.retain_logs = retain_logs
        self._cancel = False
        self._started_at = 0.0

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            ensure_packaged_runtime_paths()
            add_pipeline_to_path()
            from app import config
            from app.database.importer import import_video
            from app.database.db import get_session, init_db
            from app.database.models import SessionSummary
            import app.safety.violation_detector as violation_module
            from app.safety.pipeline import ViolationPipeline

            config.MIN_FRAMES_OVER_LIMIT_TO_FLAG = int(self.sensitivity_frames)
            violation_module.MIN_FRAMES_OVER_LIMIT_TO_FLAG = int(self.sensitivity_frames)

            calibration_path = str(calibration_path_for(self.video_path))
            if not os.path.exists(calibration_path):
                raise FileNotFoundError(f"Calibration file not found: {calibration_path}")

            self._started_at = time.perf_counter()
            emitted = {"last": 0.0}

            def on_frame(frame, stats):
                now = time.perf_counter()
                elapsed = max(now - self._started_at, 0.001)
                stats = dict(stats)
                stats["elapsed_sec"] = elapsed
                stats["fps"] = stats.get("frame_index", 0) / elapsed
                self.stats_ready.emit(stats)
                if now - emitted["last"] >= 0.03:
                    self.frame_ready.emit(self._frame_to_qimage(frame))
                    emitted["last"] = now

            def on_progress(current, total):
                self.progress_ready.emit(int(current), int(total or 0))

            pipeline = ViolationPipeline(calibration_path)
            result = pipeline.run(
                self.video_path,
                show_preview=False,
                frame_callback=on_frame,
                progress_callback=on_progress,
                stop_requested=lambda: self._cancel,
            )

            result["elapsed_sec"] = time.perf_counter() - self._started_at
            result["video_name"] = Path(self.video_path).stem
            if self._cancel or result.get("cancelled"):
                result["cancelled"] = True
                self.completed.emit(result)
                return

            import_video(result["video_name"])
            init_db()
            session = get_session()
            try:
                summary = session.query(SessionSummary).filter(SessionSummary.video_name == result["video_name"]).one_or_none()
                if summary is not None:
                    result["vehicles"] = summary.total_vehicles
                    result["violations"] = summary.total_violations
                    result["peak_speed_kmh"] = summary.peak_speed_kmh
            finally:
                session.close()

            sync = SyncManager()
            sync.mark_pending(result["video_name"])
            result["synced"] = sync.sync_video(result["video_name"])
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    @staticmethod
    def _frame_to_qimage(frame) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()


def read_video_metadata(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video: {video_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frames / fps if fps else 0.0
        return {"fps": fps, "width": width, "height": height, "frames": frames, "duration_sec": duration}
    finally:
        cap.release()
