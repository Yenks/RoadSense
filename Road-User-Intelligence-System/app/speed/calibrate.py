"""
Camera calibration — Week 5, v3 (fixed: no blocking input() during window loop).

Two-phase process:
  Phase 1: click all pixel points in the image window (no terminal interaction
           during this phase, so the window never freezes).
  Phase 2: after closing the window ('q'), enter each point's real-world
           (X, Y) in the terminal.
"""

import os
import json
import argparse

import cv2
import numpy as np

from app.config import CALIBRATION_DIR, CALIBRATION_MIN_POINTS

_pixel_points = []
_frame_for_display = None
_window_name = "Calibration - click 8+ spread-out points, 'q' to finish"


def _redraw(frame):
    display = frame.copy()
    for i, (px, py) in enumerate(_pixel_points):
        cv2.circle(display, (int(px), int(py)), 5, (0, 0, 255), -1)
        cv2.putText(display, str(i + 1), (int(px) + 8, int(py) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.imshow(_window_name, display)


def _on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _pixel_points.append((x, y))
        print(f"Point {len(_pixel_points)} clicked at pixel ({x}, {y})")
        _redraw(_frame_for_display)


def run_calibration(input_path: str, frame_index: int = 0):
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
    print("PHASE 1: Click pixel points")
    print("=" * 60)
    print(f"Need at least {CALIBRATION_MIN_POINTS} points, spread across")
    print("near/far AND left/right of the frame.")
    print("Just click — no typing yet. Press 'q' in the image window when done.")
    print("=" * 60)

    cv2.namedWindow(_window_name)
    cv2.setMouseCallback(_window_name, _on_click)
    _redraw(frame)

    while True:
        if cv2.waitKey(20) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()

    if len(_pixel_points) < CALIBRATION_MIN_POINTS:
        raise ValueError(
            f"Need at least {CALIBRATION_MIN_POINTS} points, got {len(_pixel_points)}. Re-run."
        )

    print("\n" + "=" * 60)
    print(f"PHASE 2: Enter real-world coordinates for {len(_pixel_points)} points")
    print("=" * 60)

    world_points = []
    for i, (px, py) in enumerate(_pixel_points):
        while True:
            try:
                raw = input(f"Point {i + 1} (pixel {px},{py}) -> real-world X,Y in meters: ").strip()
                wx, wy = [float(v) for v in raw.split(",")]
                world_points.append((wx, wy))
                break
            except ValueError:
                print("  Invalid format. Example: 12.5,0")

    pixel_pts = np.array(_pixel_points, dtype=np.float32)
    world_pts = np.array(world_points, dtype=np.float32)

    homography, mask = cv2.findHomography(pixel_pts, world_pts, method=cv2.RANSAC, ransacReprojThreshold=1.0)
    if homography is None:
        raise RuntimeError("Homography computation failed.")

    inlier_mask = mask.ravel().astype(bool) if mask is not None else np.ones(len(_pixel_points), dtype=bool)
    inlier_count = int(inlier_mask.sum())

    reprojected = cv2.perspectiveTransform(pixel_pts.reshape(-1, 1, 2), homography).reshape(-1, 2)
    errors_m = np.linalg.norm(reprojected - world_pts, axis=1)

    print(f"\nRANSAC inliers: {inlier_count}/{len(_pixel_points)}")
    print(f"Reprojection error — mean: {errors_m.mean():.3f}m, max: {errors_m.max():.3f}m")
    if errors_m.mean() > 0.3:
        print("WARNING: mean reprojection error > 0.3m. Consider re-clicking more carefully.")

    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(CALIBRATION_DIR, f"{base_name}_calibration.json")

    with open(output_path, "w") as f:
        json.dump({
            "type": "homography",
            "video": os.path.basename(input_path),
            "frame_index": frame_index,
            "pixel_points": _pixel_points,
            "world_points": world_points,
            "homography": homography.tolist(),
            "inlier_count": inlier_count,
            "total_points": len(_pixel_points),
            "mean_reprojection_error_m": float(errors_m.mean()),
            "max_reprojection_error_m": float(errors_m.max()),
        }, f, indent=2)

    print(f"\nSaved calibration to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Multi-point RANSAC camera calibration")
    parser.add_argument("--input", required=True)
    parser.add_argument("--frame", type=int, default=0)
    args = parser.parse_args()
    run_calibration(args.input, args.frame)


if __name__ == "__main__":
    main()