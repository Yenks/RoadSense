"""
Lightweight detection stabilizer — Week 3 upgrade (v2: velocity-aware).

Reduces frame-to-frame flicker AND lag by:
  1. Matching new detections to recent ones via IoU
  2. Showing boxes immediately (no confirm delay) once IoU-matched
  3. Predicting motion using a simple velocity estimate, so a coasting box
     (missed detection for a frame or two) moves forward with the object
     instead of freezing in place or trailing behind it
  4. Light smoothing to absorb single-frame jitter without introducing lag

Still not full tracking — Week 4's ByteTrack replaces this with proper
motion modeling, occlusion handling, and stable IDs for the whole video.
"""

from itertools import count

from app.config import (
    STABILIZER_IOU_THRESHOLD,
    STABILIZER_MIN_HITS_TO_CONFIRM,
    STABILIZER_MAX_MISSED_FRAMES,
    STABILIZER_SMOOTHING_ALPHA,
    STABILIZER_USE_VELOCITY_PREDICTION,
)


def _iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area

    return inter_area / union if union > 0 else 0.0


class _Track:
    _id_counter = count(1)

    def __init__(self, detection):
        self.id = next(_Track._id_counter)
        self.track_class = detection.track_class
        self.label = detection.label
        self.bbox = (detection.x1, detection.y1, detection.x2, detection.y2)
        self.velocity = (0.0, 0.0, 0.0, 0.0)  # dx1, dy1, dx2, dy2 per frame
        self.confidence = detection.confidence
        self.possible_rickshaw = detection.possible_rickshaw
        self.hits = 1
        self.missed = 0

    @property
    def confirmed(self):
        return self.hits >= STABILIZER_MIN_HITS_TO_CONFIRM

    def update(self, detection):
        x1, y1, x2, y2 = self.bbox
        nx1, ny1, nx2, ny2 = detection.x1, detection.y1, detection.x2, detection.y2
        a = STABILIZER_SMOOTHING_ALPHA

        new_bbox = (
            x1 + a * (nx1 - x1),
            y1 + a * (ny1 - y1),
            x2 + a * (nx2 - x2),
            y2 + a * (ny2 - y2),
        )

        # Update velocity estimate from the actual movement this frame
        if STABILIZER_USE_VELOCITY_PREDICTION:
            self.velocity = (
                new_bbox[0] - self.bbox[0],
                new_bbox[1] - self.bbox[1],
                new_bbox[2] - self.bbox[2],
                new_bbox[3] - self.bbox[3],
            )

        self.bbox = new_bbox
        self.confidence = detection.confidence
        self.label = detection.label
        self.possible_rickshaw = detection.possible_rickshaw
        self.hits += 1
        self.missed = 0

    def mark_missed(self):
        self.missed += 1
        if STABILIZER_USE_VELOCITY_PREDICTION:
            x1, y1, x2, y2 = self.bbox
            vx1, vy1, vx2, vy2 = self.velocity
            self.bbox = (x1 + vx1, y1 + vy1, x2 + vx2, y2 + vy2)


class DetectionStabilizer:
    def __init__(self):
        self.tracks = []

    def update(self, detections):
        unmatched_detections = list(detections)

        for track in self.tracks:
            best_det = None
            best_iou = STABILIZER_IOU_THRESHOLD
            for det in unmatched_detections:
                if det.track_class != track.track_class:
                    continue
                score = _iou(track.bbox, (det.x1, det.y1, det.x2, det.y2))
                if score > best_iou:
                    best_iou = score
                    best_det = det

            if best_det is not None:
                track.update(best_det)
                unmatched_detections.remove(best_det)
            else:
                track.mark_missed()

        self.tracks = [t for t in self.tracks if t.missed <= STABILIZER_MAX_MISSED_FRAMES]

        for det in unmatched_detections:
            self.tracks.append(_Track(det))

        stabilized = []
        for track in self.tracks:
            if not track.confirmed:
                continue
            x1, y1, x2, y2 = track.bbox
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            template = detections[0] if detections else None
            stabilized.append(_make_detection(template, track, x1, y1, x2, y2, cx, cy))
        return stabilized


def _make_detection(template, track, x1, y1, x2, y2, cx, cy):
    from app.detection.detector import Detection

    frame_index = template.frame_index if template else 0
    timestamp_sec = template.timestamp_sec if template else 0.0

    return Detection(
        frame_index=frame_index,
        timestamp_sec=timestamp_sec,
        track_class=track.track_class,
        label=track.label,
        confidence=round(track.confidence, 3),
        x1=round(x1, 1), y1=round(y1, 1),
        x2=round(x2, 1), y2=round(y2, 1),
        cx=round(cx, 1), cy=round(cy, 1),
        track_id=track.id,
        possible_rickshaw=track.possible_rickshaw,
    )