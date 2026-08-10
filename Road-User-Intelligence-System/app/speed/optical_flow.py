"""
Optical flow cross-check — Week 5, v2.

Independently verifies detection-based displacement using Lucas-Kanade
optical flow. If the two disagree significantly, the detection-based
measurement for that frame is distrusted (not fed into the Kalman filter's
correction step), preventing one bad detection from corrupting the track.

Honest limitation: optical flow itself is not perfect either — this is a
cross-check to catch gross disagreement, not a ground-truth oracle.
"""

import cv2
import numpy as np

from app.config import OPTICAL_FLOW_DISAGREEMENT_PX_THRESHOLD

_LK_PARAMS = dict(
    winSize=(21, 21),
    maxLevel=3,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
)


def check_agreement(prev_gray, curr_gray, prev_px, prev_py, curr_px, curr_py):
    """
    Returns True if optical flow roughly agrees with the detected displacement,
    False if they disagree beyond the threshold (measurement should be distrusted).
    Returns True (assume OK) if flow tracking itself fails, rather than blocking
    speed estimation entirely on a flow failure.
    """
    prev_pts = np.array([[[prev_px, prev_py]]], dtype=np.float32)
    next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None, **_LK_PARAMS)

    if status is None or status[0][0] != 1:
        return True  # flow failed to track — don't penalize, just skip the check

    flow_x, flow_y = next_pts[0][0]
    disagreement_px = ((flow_x - curr_px) ** 2 + (flow_y - curr_py) ** 2) ** 0.5

    return disagreement_px <= OPTICAL_FLOW_DISAGREEMENT_PX_THRESHOLD