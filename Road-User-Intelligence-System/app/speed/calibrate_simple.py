"""
Simple calibration — Week 5 (v2: multi-pair averaging for precision).

Click multiple pairs of points, each spanning your known real-world
distance, at different spots in the frame if possible. Averaging reduces
the impact of any single imprecise click.

Usage:
    python -m app.speed.calibrate_simple --input data/raw_videos/DJI_0567_720p.mp4 --frame 0 --known-distance 6.65
"""

import os
import json
import argparse
import math
import statistics

import cv2

from app.config import CALIBRATION_DIR

_pixel_points = []
_frame_for_display = None
_window_name = "Calibration - click pairs spanning the known distance, 'q' to finish"


def _redraw(frame):
    display = frame.copy()
    for i, (px, py) in enumerate(_pixel_points):
        cv2.circle(display, (int(px), int(py)), 5, (0, 0, 255), -1)
        cv2.putText(display, str(i + 1), (int(px) + 8, int(py) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        if i % 2 == 1:
            cv2.line(display, _pixel_points[i - 1], _pixel_points[i], (0, 255, 0), 1)
    cv2.imshow(_window_name, display)


def _on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        _pixel_points.append((x, y))
        pair_num = (len(_pixel_points) + 1) // 2
        side = "start" if len(_pixel_points) % 2 == 1 else "end"
        print(f"Pair {pair_num} {side} point: ({x}, {y})")
        _redraw(_frame_for_display)


def run_simple_calibration(input_path: str, known_distance_m: float, frame_index: int = 0):
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
    print("CALIBRATION — multi-pair averaging")
    print("=" * 60)
    print(f"Known real-world distance: {known_distance_m} m")
    print("Click PAIRS of points, each pair spanning that known distance.")
    print("For best accuracy, click 3+ pairs at DIFFERENT spots in the frame")
    print("if the same known distance repeats visually (e.g. multiple")
    print("crossing stripes), otherwise click the same distance 3+ times")
    print("as carefully as possible for a precision average.")
    print("Press 'q' once done (need at least 1 pair, 3+ recommended).")
    print("=" * 60)

    cv2.namedWindow(_window_name)
    cv2.setMouseCallback(_window_name, _on_click)
    _redraw(frame)

    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"):
            break
    cv2.destroyAllWindows()

    if len(_pixel_points) < 2 or len(_pixel_points) % 2 != 0:
        raise ValueError(
            f"Need an even number of points (pairs), got {len(_pixel_points)}. Re-run calibration."
        )

    scales = []
    for i in range(0, len(_pixel_points), 2):
        (x1, y1), (x2, y2) = _pixel_points[i], _pixel_points[i + 1]
        pixel_distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if pixel_distance == 0:
            continue
        scales.append(pixel_distance / known_distance_m)

    if not scales:
        raise ValueError("No valid pairs measured (all had zero distance).")

    pixels_per_meter = statistics.mean(scales)
    std_dev = statistics.stdev(scales) if len(scales) > 1 else 0.0
    pct_spread = (std_dev / pixels_per_meter * 100) if pixels_per_meter else 0.0

    print(f"\nPairs measured: {len(scales)}")
    print(f"Individual scales: {[round(s, 2) for s in scales]}")
    print(f"Averaged scale: {pixels_per_meter:.2f} px/m (std dev: {std_dev:.2f}, ~{pct_spread:.1f}% spread)")
    if pct_spread > 5:
        print("WARNING: your click pairs disagree by more than 5% — consider re-clicking more carefully,")
        print("or zooming in on the video frame before running this for tighter precision.")

    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(CALIBRATION_DIR, f"{base_name}_calibration.json")

    with open(output_path, "w") as f:
        json.dump({
            "type": "simple_scale",
            "video": os.path.basename(input_path),
            "frame_index": frame_index,
            "pixel_pairs": _pixel_points,
            "known_distance_m": known_distance_m,
            "individual_scales": scales,
            "pixels_per_meter": pixels_per_meter,
            "scale_std_dev": std_dev,
        }, f, indent=2)

    print(f"Saved calibration to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Multi-pair averaging camera calibration")
    parser.add_argument("--input", required=True)
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--known-distance", type=float, required=True)
    args = parser.parse_args()
    run_simple_calibration(args.input, args.known_distance, args.frame)


if __name__ == "__main__":
    main()
    