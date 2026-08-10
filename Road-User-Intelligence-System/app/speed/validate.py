"""
Accuracy validation — Week 5.

Compares the system's reported speed for a specific track/time window
against a manually measured ground-truth speed YOU provide. Appends each
comparison to a running accuracy report so you build real evidence of
accuracy over multiple checks, instead of a single unverified claim.

Usage:
    python -m app.speed.validate --log data/processed/DJI_0567_720p_week5_speed.json
"""

import argparse
import csv
import json
import os
import statistics

from app.config import PROCESSED_DIR


def load_log(log_path):
    with open(log_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Validate speed accuracy against manual ground truth")
    parser.add_argument("--log", required=True, help="Path to a *_week5_speed.json log")
    args = parser.parse_args()

    records = load_log(args.log)
    report_path = os.path.join(PROCESSED_DIR, "accuracy_report.csv")

    print("=" * 60)
    print("SPEED ACCURACY VALIDATION")
    print("=" * 60)
    print("For each check: pick a track_id and time window you can verify")
    print("independently (known-speed drive-through, GPS app, etc), and")
    print("enter the real speed. Type 'done' when finished.")
    print("=" * 60)

    results = []
    while True:
        track_id_raw = input("\nTrack ID to check (or 'done'): ").strip()
        if track_id_raw.lower() == "done":
            break
        try:
            track_id = int(track_id_raw)
        except ValueError:
            print("  Invalid track ID.")
            continue

        t_start = float(input("  Window start (seconds): ").strip())
        t_end = float(input("  Window end (seconds): ").strip())
        manual_speed = float(input("  Manually measured/known speed (km/h): ").strip())

        matching = [
            r for r in records
            if r["track_id"] == track_id
            and t_start <= r["timestamp_sec"] <= t_end
            and r.get("speed_kmh") is not None
        ]

        if not matching:
            print(f"  No system speed readings found for track {track_id} in that window.")
            continue

        system_speeds = [r["speed_kmh"] for r in matching]
        system_mean = statistics.mean(system_speeds)
        error_kmh = system_mean - manual_speed
        pct_error = (abs(error_kmh) / manual_speed * 100) if manual_speed > 0 else float("nan")

        print(f"  System mean: {system_mean:.1f} km/h | Manual: {manual_speed:.1f} km/h "
              f"| Error: {error_kmh:+.1f} km/h ({pct_error:.1f}%)")

        results.append({
            "track_id": track_id,
            "t_start": t_start,
            "t_end": t_end,
            "manual_speed_kmh": manual_speed,
            "system_speed_kmh": round(system_mean, 1),
            "error_kmh": round(error_kmh, 1),
            "pct_error": round(pct_error, 1),
        })

    if not results:
        print("\nNo checks recorded.")
        return

    file_exists = os.path.exists(report_path)
    with open(report_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)

    all_pct_errors = [r["pct_error"] for r in results if r["pct_error"] == r["pct_error"]]  # drop NaN
    print("\n" + "=" * 60)
    print(f"This session: {len(results)} checks, mean % error: {statistics.mean(all_pct_errors):.1f}%")
    print(f"Appended to: {report_path}")
    print("Run this multiple times across different vehicles/videos to build")
    print("a real, evidence-based accuracy figure for your report.")
    print("=" * 60)


if __name__ == "__main__":
    main()