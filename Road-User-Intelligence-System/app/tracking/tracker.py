"""
Tracking module — Week 4.

Wraps ByteTrack (via the `supervision` library) to assign persistent
track IDs across frames. Unlike Week 3's stabilizer, this handles proper
motion association and survives short occlusions (an object briefly
hidden behind another object or a tree keeps its ID instead of getting
a brand-new one).
"""

import numpy as np
import supervision as sv

from app.config import (
    TRACK_ACTIVATION_THRESHOLD,
    LOST_TRACK_BUFFER,
    MINIMUM_MATCHING_THRESHOLD,
)


class SchoolZoneTracker:
    def __init__(self, frame_rate: int = 30):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=TRACK_ACTIVATION_THRESHOLD,
            lost_track_buffer=LOST_TRACK_BUFFER,
            minimum_matching_threshold=MINIMUM_MATCHING_THRESHOLD,
            frame_rate=frame_rate,
        )

    def update(self, boxes_xyxy, confidences, class_ids):
        """
        boxes_xyxy: list/array of [x1, y1, x2, y2]
        confidences: list/array of floats
        class_ids: list/array of ints

        Returns a supervision Detections object with a `.tracker_id` array
        aligned to the returned (possibly filtered/reordered) boxes.
        """
        if len(boxes_xyxy) == 0:
            detections = sv.Detections.empty()
        else:
            detections = sv.Detections(
                xyxy=np.array(boxes_xyxy, dtype=float),
                confidence=np.array(confidences, dtype=float),
                class_id=np.array(class_ids, dtype=int),
            )

        return self.tracker.update_with_detections(detections)