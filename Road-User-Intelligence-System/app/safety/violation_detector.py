"""
Speed violation detection — Week 6.

Watches tracked vehicles' speed_kmh values (from Week 5) and flags a
violation once a track has been measured over the speed limit for
MIN_FRAMES_OVER_LIMIT_TO_FLAG consecutive/total frames — avoiding a
single noisy speed reading from triggering a false violation.

Each violation is logged once per track (not once per frame), with the
track's peak recorded speed, and a snapshot image is saved of that
vehicle at the moment of detection.
"""

import os
import json
import csv
from dataclasses import dataclass, asdict

import cv2

from app.config import SPEED_LIMIT_KMH, VIOLATIONS_DIR, VIOLATION_SNAPSHOT_PADDING_PX, MIN_FRAMES_OVER_LIMIT_TO_FLAG, YIELD_SPEED_THRESHOLD_KMH
from app.config import YIELD_SPEED_THRESHOLD_KMH

@dataclass
class Violation:
    track_id: int
    label: str
    frame_index: int
    timestamp_sec: float
    peak_speed_kmh: float
    speed_limit_kmh: float
    snapshot_path: str
    violation_type: str = "speeding"  # or "failure_to_yield"


class ViolationDetector:
    def __init__(self, output_dir: str, speed_limit_kmh: float = SPEED_LIMIT_KMH):
        self.speed_limit_kmh = speed_limit_kmh
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self._over_limit_counts = {}   # track_id -> consecutive frames over limit
        self._already_flagged = set()  # track_ids already logged as a violation
        self._peak_speed = {}          # track_id -> highest speed seen

        self.violations = []

    def update(self, frame, detections):
        """
        frame: current video frame (for snapshot cropping)
        detections: list of Detection objects for this frame (post-tracking, with speed_kmh)
        """
        for det in detections:
            if det.track_class != "vehicle" or det.track_id is None or det.track_id < 0:
                continue
            if det.speed_kmh is None:
                continue

            self._peak_speed[det.track_id] = max(
                self._peak_speed.get(det.track_id, 0.0), det.speed_kmh
            )

            if det.speed_kmh > self.speed_limit_kmh:
                self._over_limit_counts[det.track_id] = self._over_limit_counts.get(det.track_id, 0) + 1
            else:
                self._over_limit_counts[det.track_id] = 0

            should_flag = (
                self._over_limit_counts.get(det.track_id, 0) >= MIN_FRAMES_OVER_LIMIT_TO_FLAG
                and det.track_id not in self._already_flagged
            )

            if should_flag:
                self._already_flagged.add(det.track_id)
                snapshot_path = self._save_snapshot(frame, det)
                violation = Violation(
                    track_id=det.track_id,
                    label=det.label,
                    frame_index=det.frame_index,
                    timestamp_sec=det.timestamp_sec,
                    peak_speed_kmh=round(self._peak_speed[det.track_id], 1),
                    speed_limit_kmh=self.speed_limit_kmh,
                    snapshot_path=snapshot_path,
                )
                self.violations.append(violation)

    def _save_snapshot(self, frame, det) -> str:
        pad = VIOLATION_SNAPSHOT_PADDING_PX
        h, w = frame.shape[:2]
        x1 = max(int(det.x1) - pad, 0)
        y1 = max(int(det.y1) - pad, 0)
        x2 = min(int(det.x2) + pad, w)
        y2 = min(int(det.y2) + pad, h)

        crop = frame[y1:y2, x1:x2]
        filename = f"violation_track{det.track_id}_{det.label}_{det.speed_kmh:.0f}kmh.jpg"
        path = os.path.join(self.output_dir, filename)
        cv2.imwrite(path, crop)
        return path

    def save_logs(self, base_name: str, processed_dir: str):
        json_path = os.path.join(processed_dir, f"{base_name}_week6_violations.json")
        csv_path = os.path.join(processed_dir, f"{base_name}_week6_violations.csv")

        records = [asdict(v) for v in self.violations]
        with open(json_path, "w") as jf:
            json.dump(records, jf, indent=2)

        if records:
            with open(csv_path, "w", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)

        return json_path, csv_path

    def summary(self) -> dict:
        return {
            "total_violations": len(self.violations),
            "speed_limit_kmh": self.speed_limit_kmh,
            "by_label": self._count_by_label(),
        }

    def _count_by_label(self):
        counts = {}
        for v in self.violations:
            counts[v.label] = counts.get(v.label, 0) + 1
        return counts
    def check_yield_violation(self, frame, det, pedestrian_present: bool, crossing_monitor):
        """Separate from the speeding check — flags failure to yield to a
        pedestrian on the crossing, per Act 683 / L.I. 2180 Sec 73(1)."""
        if det.track_class != "vehicle" or det.track_id is None or det.track_id < 0:
            return
        if det.speed_kmh is None:
            return
        if not pedestrian_present:
            return
        if not crossing_monitor.vehicle_in_crossing_zone(det.cx, det.cy):
            return
        if det.speed_kmh <= YIELD_SPEED_THRESHOLD_KMH:
            return  # effectively yielding/stopping — compliant

        flag_key = f"yield_{det.track_id}"
        if flag_key in self._already_flagged:
            return
        self._already_flagged.add(flag_key)

        snapshot_path = self._save_snapshot(frame, det)
        self.violations.append(Violation(
            track_id=det.track_id,
            label=det.label,
            frame_index=det.frame_index,
            timestamp_sec=det.timestamp_sec,
            peak_speed_kmh=det.speed_kmh,
            speed_limit_kmh=YIELD_SPEED_THRESHOLD_KMH,
            snapshot_path=snapshot_path,
            violation_type="failure_to_yield",
        ))