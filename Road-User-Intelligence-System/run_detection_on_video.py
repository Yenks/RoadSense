"""
Week 3 test driver.

Runs the YOLOv8 detector over a video file, prints per-frame counts,
and writes an annotated .mp4 you can watch to visually verify detections.

Usage:
    python run_detection_on_video.py --input data/raw_videos/sample.mp4 \
                                      --output data/processed/sample_annotated.mp4 \
                                      --sample-every 1
"""

import argparse
import time

from app.detection.detector import VehiclePedestrianDetector
from app.utils.video_utils import open_video, frame_generator, get_video_writer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input video")
    parser.add_argument("--output", required=True, help="Path to save annotated video")
    parser.add_argument("--sample-every", type=int, default=1,
                         help="Process every Nth frame (speeds up CPU testing)")
    parser.add_argument("--max-frames", type=int, default=None,
                         help="Stop early after this many processed frames (dev testing)")
    args = parser.parse_args()

    print(f"Loading detector...")
    detector = VehiclePedestrianDetector()

    print(f"Opening video: {args.input}")
    cap, meta = open_video(args.input)
    print(f"  fps={meta['fps']:.1f} size={meta['width']}x{meta['height']} frames={meta['frame_count']}")

    writer = get_video_writer(args.output, meta["fps"], meta["width"], meta["height"])

    frame_count = 0
    total_detections = 0
    class_totals = {}
    t0 = time.time()

    for idx, frame in frame_generator(cap, sample_every=args.sample_every):
        detections = detector.detect(frame)
        annotated = detector.annotate(frame, detections)
        writer.write(annotated)

        frame_count += 1
        total_detections += len(detections)
        for d in detections:
            class_totals[d.class_name] = class_totals.get(d.class_name, 0) + 1

        if frame_count % 25 == 0:
            counts_str = ", ".join(f"{k}:{v}" for k, v in
                                    sorted(class_totals.items()))
            print(f"  frame {idx}: processed={frame_count}, "
                  f"this_frame_detections={len(detections)}, running_totals=({counts_str})")

        if args.max_frames and frame_count >= args.max_frames:
            print(f"Reached --max-frames={args.max_frames}, stopping early.")
            break

    writer.release()
    elapsed = time.time() - t0

    print("\n--- Summary ---")
    print(f"Frames processed : {frame_count}")
    print(f"Elapsed time     : {elapsed:.1f}s ({frame_count / elapsed:.2f} fps)")
    print(f"Total detections : {total_detections}")
    for cls, count in sorted(class_totals.items(), key=lambda x: -x[1]):
        print(f"  {cls:12s}: {count}")
    print(f"\nAnnotated video saved to: {args.output}")


if __name__ == "__main__":
    main()