"""
Optional rickshaw verification using a real trained model (Roboflow Universe).
Disabled by default. Only called on crops the local heuristic already flagged,
so it doesn't slow down the main detection pass.

Setup if you want this:
    pip install inference-sdk
    Get a free API key at https://app.roboflow.com -> paste into app/config.py
"""

import cv2

from app.config import (
    ENABLE_ROBOFLOW_RICKSHAW_CHECK,
    ROBOFLOW_API_KEY,
    ROBOFLOW_MODEL_ID,
)

_client = None


def _get_client():
    global _client
    if _client is None:
        from inference_sdk import InferenceHTTPClient
        _client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key=ROBOFLOW_API_KEY,
        )
    return _client


def verify_rickshaw_crop(frame, x1: float, y1: float, x2: float, y2: float) -> bool:
    """Returns True if the trained model confirms a rickshaw in this crop."""
    if not ENABLE_ROBOFLOW_RICKSHAW_CHECK:
        return False  # heuristic flag stands as-is if verification is off

    crop = frame[max(int(y1), 0):int(y2), max(int(x1), 0):int(x2)]
    if crop.size == 0:
        return False

    tmp_path = "/tmp/_rickshaw_check.jpg"
    cv2.imwrite(tmp_path, crop)

    try:
        client = _get_client()
        result = client.infer(tmp_path, model_id=ROBOFLOW_MODEL_ID)
        predictions = result.get("predictions", [])
        return len(predictions) > 0
    except Exception as e:
        print(f"[RickshawVerifier] Skipped (error: {e})")
        return False