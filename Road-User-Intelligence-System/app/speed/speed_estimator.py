"""
Speed estimation — Week 5, FINAL+fix.

Adds a validity-region check: speed is only computed while a vehicle's
position is within (or near) the calibrated zone. Outside that region,
the homography/scale was never verified and can extrapolate to wildly
wrong values — confirmed by DJI_0538 producing 149km/h+ readings from
vehicles ~100-500px outside the calibrated quadrilateral, regardless of
calibration accuracy.
"""

import json
import os
from collections import deque

import numpy as np
import cv2

from app.config import (
    SPEED_HISTORY_SECONDS,
    MIN_TRACK_POINTS_FOR_SPEED,
    SPEED_SMOOTHING_ALPHA,
    MAX_PLAUSIBLE_SPEED_KMH,
    MIN_PLAUSIBLE_SPEED_KMH,
    SPEED_VALID_REGION_BUFFER_METERS,
)


class SpeedEstimator:
    def __init__(self, calibration_path: str):
        if not os.path.exists(calibration_path):
            raise FileNotFoundError(
                f"Calibration file not found: {calibration_path}\n"
                f"Run calibrate.py, calibrate_simple.py, or calibrate_rect.py first."
            )
        with open(calibration_path) as f:
            data = json.load(f)

        self.calibration_type = data.get("type", "homography")
        if self.calibration_type == "simple_scale":
            self.pixels_per_meter = data["pixels_per_meter"]
            self.homography = None
        else:
            self.homography = np.array(data["homography"], dtype=np.float64)
            self.pixels_per_meter = None

        # Build the valid region polygon (if the calibration has pixel corner
        # points — true for calibrate_rect.py and calibrate.py, not for
        # calibrate_simple.py's 2-point method)
        self.valid_region_px = None
        if "pixel_points" in data:
            points = np.array(data["pixel_points"], dtype=np.float32)
            width_m = data.get("width_m")
            if width_m:
                px_width = np.linalg.norm(points[1] - points[0])
                px_per_meter_est = px_width / width_m
                buffer_px = SPEED_VALID_REGION_BUFFER_METERS * px_per_meter_est
            else:
                buffer_px = 50.0  # fallback margin if no width_m available
            self.valid_region_px = self._expand_polygon(points, buffer_px)

        self._history = {}
        self._smoothed_speed = {}

    def _expand_polygon(self, polygon, margin_px):
        centroid = polygon.mean(axis=0)
        expanded = []
        for point in polygon:
            direction = point - centroid
            norm = np.linalg.norm(direction)
            if norm == 0:
                expanded.append(point)
                continue
            expanded.append(point + (direction / norm) * margin_px)
        return np.array(expanded, dtype=np.float32)

    def _in_valid_region(self, px, py) -> bool:
        if self.valid_region_px is None:
            return True  # no region data available — can't restrict, allow through
        return cv2.pointPolygonTest(self.valid_region_px, (float(px), float(py)), False) >= 0

    def pixel_to_world(self, px: float, py: float):
        if self.calibration_type == "simple_scale":
            return px / self.pixels_per_meter, py / self.pixels_per_meter
        point = np.array([[[px, py]]], dtype=np.float64)
        world = cv2.perspectiveTransform(point, self.homography)
        return float(world[0][0][0]), float(world[0][0][1])

    def update(self, track_id: int, timestamp_sec: float, px: float, py: float):
        if not self._in_valid_region(px, py):
            return None  # outside the calibrated/verified zone — don't extrapolate

        wx, wy = self.pixel_to_world(px, py)

        history = self._history.setdefault(track_id, deque())
        history.append((timestamp_sec, wx, wy))
        while history and (timestamp_sec - history[0][0]) > SPEED_HISTORY_SECONDS:
            history.popleft()

        if len(history) < MIN_TRACK_POINTS_FOR_SPEED:
            return None

        times = np.array([p[0] for p in history])
        xs = np.array([p[1] for p in history])
        ys = np.array([p[2] for p in history])

        t_centered = times - times.mean()
        denom = np.sum(t_centered ** 2)
        if denom == 0:
            return None

        vx = np.sum(t_centered * (xs - xs.mean())) / denom
        vy = np.sum(t_centered * (ys - ys.mean())) / denom
        speed_kmh = ((vx ** 2 + vy ** 2) ** 0.5) * 3.6

        if speed_kmh > MAX_PLAUSIBLE_SPEED_KMH:
            return None
        if speed_kmh < MIN_PLAUSIBLE_SPEED_KMH:
            speed_kmh = 0.0

        prev = self._smoothed_speed.get(track_id, speed_kmh)
        smoothed = prev + SPEED_SMOOTHING_ALPHA * (speed_kmh - prev)
        self._smoothed_speed[track_id] = smoothed
        return round(smoothed, 1)

    def cleanup(self, active_track_ids):
        stale = [tid for tid in self._history if tid not in active_track_ids]
        for tid in stale:
            del self._history[tid]
            self._smoothed_speed.pop(tid, None)