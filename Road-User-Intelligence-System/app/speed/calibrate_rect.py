"""
4-point rectangle calibration — Week 5, v4 (matches Roboflow's published
ViewTransformer method: https://blog.roboflow.com/estimate-speed-computer-vision/).

Click the 4 corners of a real-world rectangle (e.g. the zebra crossing)
in the video frame, in this exact order:
  1. Near-left corner
  2. Near-right corner
  3. Far-right corner
  4. Far-left corner
("Near" = closer to camera/bottom of frame, "far" = further away)

Then enter the rectangle's real WIDTH and LENGTH in meters.
Uses cv2.getPerspectiveTransform (same matrix type as full homography),
so the existing SpeedEstimator works with this calibration unchanged.
"""

import os
import json
import argparse

import cv2
import numpy as np

from app.config import CALIBRATION_DIR

_pixel_points = []
_frame_for_display = None
_window_name = "Click 4 corners: near-left, near-right, far-right, far-left. 'q' to finish"


def _redraw(frame):
    display = frame.copy()
    labels = ["near-left", "near-right", "far-right", "far-left"]
    for i, (px, py) in enumerate(_pixel_points):
        cv2.circle(display, (int(px), int(py)), 6, (0, 0, 255), -1)
        label = labels[i] if i < len(labels) else str(i + 1)
        cv2.putText(display, f"{i+1}:{label}", (int(px) + 10, int(py) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    if len(_pixel_points) >= 2:
        pts = np.array(_pixel_points, dtype=np.int32)
        cv2.polylines(display, [pts], isClosed=(len(_pixel_points) == 4),
                       color=(0, 255, 0), thickness=1)
    cv2.imshow(_window_name, display)


def _on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(_pixel_points) < 4:
        _pixel_points.append((x, y))
        labels = ["near-left", "near-right", "far-right", "far-left"]
        print(f"Point {len(_pixel_points)} ({labels[len(_pixel_points)-1]}): pixel ({x}, {y})")
        _redraw(_frame_for_display)


def run_calibration(input_path: str, width_m: float, length_m: float, frame_index: int = 0):
    global _frame_for_display

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video: {input_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise IOError(f"Could not read frame {frame_index} from {input_path}")

    _frame_for_display = frame

    print("=" * 60)
    print("4-POINT RECTANGLE CALIBRATION")
    print("=" * 60)
    print(f"Rectangle: {width_m}m wide x {length_m}m long")
    print("Click IN ORDER: near-left, near-right, far-right, far-left")
    print("(this should trace the crossing's outline as a quadrilateral)")
    print("Press 'q' once all 4 points are placed.")
    print("=" * 60)

    cv2.namedWindow(_window_name)
    cv2.setMouseCallback(_window_name, _on_click)
    _redraw(frame)

    while True:
        if cv2.waitKey(20) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()

    if len(_pixel_points) != 4:
        raise ValueError(f"Need exactly 4 points, got {len(_pixel_points)}. Re-run.")

    source = np.array(_pixel_points, dtype=np.float32)
    target = np.array([
        [0, 0],
        [width_m, 0],
        [width_m, length_m],
        [0, length_m],
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(source, target)

    # Reprojection check — even with only 4 points, worth confirming the
    # math round-trips cleanly (source clicks perfectly map to target corners
    # by construction, but this at least confirms no degenerate/collinear points)
    reprojected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    errors_m = np.linalg.norm(reprojected - target, axis=1)
    print(f"\nReprojection check — max error: {errors_m.max():.4f}m (should be ~0, confirms valid transform)")

    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(CALIBRATION_DIR, f"{base_name}_calibration.json")

    with open(output_path, "w") as f:
        json.dump({
            "type": "homography",  # same matrix format as full homography — reuses existing SpeedEstimator
            "method": "4point_rectangle",
            "video": os.path.basename(input_path),
            "frame_index": frame_index,
            "pixel_points": _pixel_points,
            "width_m": width_m,
            "length_m": length_m,
            "homography": matrix.tolist(),
        }, f, indent=2)

    print(f"Saved calibration to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="4-point rectangle calibration (Roboflow ViewTransformer method)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--width", type=float, required=True, help="Real-world width in meters")
    parser.add_argument("--length", type=float, required=True, help="Real-world length in meters")
    args = parser.parse_args()
    run_calibration(args.input, args.width, args.length, args.frame)


if __name__ == "__main__":
    main()