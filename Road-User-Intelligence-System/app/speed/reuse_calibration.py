"""
Calibration reuse — copies an existing calibration to a new video that
shares the same physical crossing/camera position, avoiding a repeat
manual calibration for footage from a location already calibrated.

Only valid if the new video is genuinely the same crossing, same camera
position/altitude as the source calibration — otherwise this silently
applies the wrong scale. When in doubt, calibrate fresh instead.

Usage:
    python -m app.speed.reuse_calibration --source DJI_0567_720p --target DJI_0601_720p
"""

import os
import json
import argparse

from app.config import CALIBRATION_DIR


def reuse_calibration(source_video: str, target_video: str):
    source_path = os.path.join(CALIBRATION_DIR, f"{source_video}_calibration.json")
    target_path = os.path.join(CALIBRATION_DIR, f"{target_video}_calibration.json")

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"No calibration found for '{source_video}'. Calibrate it first.")

    if os.path.exists(target_path):
        confirm = input(f"'{target_video}' already has a calibration. Overwrite? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

    with open(source_path) as f:
        data = json.load(f)

    data["video"] = f"{target_video}.mp4"
    data["reused_from"] = source_video  # traceable — shows this wasn't independently calibrated

    with open(target_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Calibration reused: '{source_video}' -> '{target_video}'")
    print(f"Saved to: {target_path}")


def main():
    parser = argparse.ArgumentParser(description="Reuse an existing calibration for a same-location video")
    parser.add_argument("--source", required=True, help="Base name of the already-calibrated video")
    parser.add_argument("--target", required=True, help="Base name of the new video (same crossing/position)")
    args = parser.parse_args()
    reuse_calibration(args.source, args.target)


if __name__ == "__main__":
    main()