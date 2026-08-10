"""
Box smoother — Week 5.

ByteTrack gives persistent IDs but does NOT smooth box position — raw
per-frame detection noise still makes boxes appear to jitter/wobble even
on a stationary or steady-moving object. This applies simple EMA smoothing
keyed by track_id (no re-matching needed, ByteTrack's ID is already stable).
"""

from app.config import BOX_SMOOTHING_ALPHA


class BoxSmoother:
    def __init__(self, alpha: float = BOX_SMOOTHING_ALPHA):
        self.alpha = alpha
        self._smoothed = {}  # track_id -> (x1, y1, x2, y2)

    def update(self, track_id: int, bbox):
        x1, y1, x2, y2 = bbox
        if track_id not in self._smoothed:
            self._smoothed[track_id] = bbox
        else:
            px1, py1, px2, py2 = self._smoothed[track_id]
            a = self.alpha
            self._smoothed[track_id] = (
                px1 + a * (x1 - px1),
                py1 + a * (y1 - py1),
                px2 + a * (x2 - px2),
                py2 + a * (y2 - py2),
            )
        return self._smoothed[track_id]

    def cleanup(self, active_track_ids):
        stale = [tid for tid in self._smoothed if tid not in active_track_ids]
        for tid in stale:
            del self._smoothed[tid]