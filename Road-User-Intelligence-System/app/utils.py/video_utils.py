"""
Small helpers for reading/writing video and iterating frames.
Kept dependency-light (just OpenCV) so it's reusable by tracking,
speed estimation, etc. in later weeks.
"""

import os
import cv2


def open_video(path):
    """Open a video file and return (cap, meta) or raise if it can't be opened."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Video not found: {path}")

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"Could not open video: {path}")

    meta = {
        "fps": cap.get(cv2.CAP_PROP_FPS) or 0,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    return cap, meta


def frame_generator(cap, sample_every=1):
    """
    Yield (frame_index, frame) from an opened cv2.VideoCapture.
    sample_every=N skips frames to speed up dev-time testing on CPU.
    """
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % sample_every == 0:
            yield idx, frame
        idx += 1
    cap.release()


def get_video_writer(output_path, fps, width, height):
    """Create an mp4 writer for saving annotated output."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fourcc = cv2.cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, fps if fps > 0 else 25, (width, height))