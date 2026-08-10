"""
Vehicle counter — Week 4.

Counts a vehicle once its track has been confirmed (seen in at least
TRACK_CONFIRM_HITS_FOR_COUNT frames), not on first appearance, so a single
flickered false-positive doesn't inflate the count.

To switch to line-crossing counting later: replace the confirm-hits check
in `update()` with a check of whether the track's center (d.cx, d.cy)
crossed a defined line between the previous and current frame. Everything
else (counted_ids bookkeeping, summary output) stays the same.
"""

from collections import defaultdict

from app.config import TRACK_CONFIRM_HITS_FOR_COUNT


class VehicleCounter:
    def __init__(self, confirm_hits: int = TRACK_CONFIRM_HITS_FOR_COUNT):
        self.confirm_hits = confirm_hits
        self._hit_counts = {}       # track_id -> number of frames seen
        self._counted_ids = set()   # track_ids already counted
        self.counts_by_label = defaultdict(int)
        self.total_count = 0

    def update(self, detections):
        """detections: list of Detection objects for the current frame (post-tracking)."""
        for det in detections:
            if det.track_class != "vehicle":
                continue
            if det.track_id is None or det.track_id < 0:
                continue

            self._hit_counts[det.track_id] = self._hit_counts.get(det.track_id, 0) + 1

            if (det.track_id not in self._counted_ids
                    and self._hit_counts[det.track_id] >= self.confirm_hits):
                self._counted_ids.add(det.track_id)
                self.counts_by_label[det.label] += 1
                self.total_count += 1

    def summary(self) -> dict:
        return {
            "total_vehicles": self.total_count,
            "by_label": dict(self.counts_by_label),
        }