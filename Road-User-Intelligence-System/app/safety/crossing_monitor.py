"""
Crossing / yield monitoring — Week 6-7 combined.

Reuses the ACTUAL calibration corners (the same 4 points you clicked for
speed calibration) as the crossing zone geometry — no separate guessed
polygon. Two violation types:

  "speeding"        — vehicle over SPEED_LIMIT_KMH, no pedestrian involved
                       (same as Week 6's original violation detector)
  "failure_to_yield"— vehicle moving above YIELD_SPEED_THRESHOLD_KMH while
                       inside the crossing zone AND a pedestrian is at/on
                       the crossing — citing Act 683 / L.I. 2180 Sec 73(1)
"""

import json
import numpy as np
import cv2

from app.config import (
    APPROACH_ZONE_EXTRA_METERS,
    YIELD_SPEED_THRESHOLD_KMH,
    PEDESTRIAN_CROSSING_BUFFER_METERS,
)


class CrossingMonitor:
    def __init__(self, calibration_path: str):
        with open(calibration_path) as f:
            data = json.load(f)

        self.crossing_polygon_px = np.array(data["pixel_points"], dtype=np.float32)  # the 4 clicked corners
        width_m = data.get("width_m")
        length_m = data.get("length_m")

        # Rough pixels-per-meter for sizing buffers (approximate — real scale
        # varies across the frame due to perspective, this is a reasonable
        # local estimate near the crossing zone itself)
        px_width = np.linalg.norm(self.crossing_polygon_px[1] - self.crossing_polygon_px[0])
        self.px_per_meter = (px_width / width_m) if width_m else 20.0

        self.approach_polygon_px = self._expand_polygon(
            self.crossing_polygon_px, APPROACH_ZONE_EXTRA_METERS * self.px_per_meter
        )
        self.pedestrian_zone_px = self._expand_polygon(
            self.crossing_polygon_px, PEDESTRIAN_CROSSING_BUFFER_METERS * self.px_per_meter
        )

    def _expand_polygon(self, polygon, margin_px):
        """Pushes each vertex outward from the polygon's centroid by margin_px.
        A simple approximation of dilating the zone outward — not
        perspective-perfect, but adequate for a proximity buffer."""
        centroid = polygon.mean(axis=0)
        expanded = []
        for point in polygon:
            direction = point - centroid
            norm = np.linalg.norm(direction)
            if norm == 0:
                expanded.append(point)
                continue
            unit = direction / norm
            expanded.append(point + unit * margin_px)
        return np.array(expanded, dtype=np.float32)

    def _point_in_polygon(self, polygon, x, y) -> bool:
        return cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0

    def vehicle_in_crossing_zone(self, x, y) -> bool:
        return self._point_in_polygon(self.crossing_polygon_px, x, y)

    def vehicle_in_approach_zone(self, x, y) -> bool:
        return self._point_in_polygon(self.approach_polygon_px, x, y)

    def pedestrian_at_crossing(self, x, y) -> bool:
        return self._point_in_polygon(self.pedestrian_zone_px, x, y)

    def any_pedestrian_present(self, detections) -> bool:
        for det in detections:
            if det.track_class == "pedestrian" and self.pedestrian_at_crossing(det.cx, det.cy):
                return True
        return False

    def draw_zones(self, frame):
        cv2.polylines(frame, [self.crossing_polygon_px.astype(np.int32)], True, (255, 200, 0), 2)
        cv2.polylines(frame, [self.approach_polygon_px.astype(np.int32)], True, (100, 100, 255), 1)
        return frame