"""
Extracts frame 0 from every video in the manifest marked NEW, saving
them as images for easy side-by-side reference while gathering Google
Maps measurements.

Usage:
    python extract_frames.py
"""

import csv
import os
import cv2

MANIFEST_PATH = "video_manifest.csv"
VIDEO_DIR = os.path.join("data", "raw_videos")
OUTPUT_DIR = os.path.join("data", "calibration_frames")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(MANIFEST_PATH) as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if row["calibration_source"].strip() != "NEW":
            continue

        video_name = row["video_name"].strip()
        input_path = os.path.join(VIDEO_DIR, f"{video_name}.mp4")

        if not os.path.exists(input_path):
            print(f"SKIP: {video_name} — file not found")
            continue

        cap = cv2.VideoCapture(input_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            print(f"SKIP: {video_name} — could not read frame")
            continue

        out_path = os.path.join(OUTPUT_DIR, f"{video_name}_frame0.jpg")
        cv2.imwrite(out_path, frame)
        print(f"Saved: {out_path}")

    print(f"\nAll frames saved to: {OUTPUT_DIR}")
    print("Open that folder to see every new crossing at a glance.")


if __name__ == "__main__":
    main()