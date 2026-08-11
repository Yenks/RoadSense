"""
Violation detection pipeline — Week 6-7 combined.

Detection -> ByteTrack -> box smoothing -> speed estimation -> two violation
checks:
  1. Speeding (Week 6) — vehicle over SPEED_LIMIT_KMH
  2. Failure to yield (Week 7) — vehicle moving through the crossing zone
     while a pedestrian is present, above YIELD_SPEED_THRESHOLD_KMH
Produces annotated video + logs + violation snapshots.
"""

import os
import csv
import json
import argparse
from dataclasses import asdict

import cv2
from tqdm import tqdm

from app.config import PROCESSED_DIR, CALIBRATION_DIR, VIOLATIONS_DIR, SPEED_LIMIT_KMH, GROUND_POINT_MODE
from app.detection.detector import SchoolZoneDetector, Detection
from app.detection.rider_pairing import pair_riders
from app.tracking.tracker import SchoolZoneTracker
from app.tracking.vehicle_counter import VehicleCounter
from app.tracking.box_smoother import BoxSmoother
from app.speed.speed_estimator import SpeedEstimator
from app.safety.violation_detector import ViolationDetector
from app.safety.crossing_monitor import CrossingMonitor

COLOR_VEHICLE = (0, 140, 255)
COLOR_VIOLATION = (0, 0, 255)
COLOR_PEDESTRIAN = (60, 220, 60)
COLOR_RIDER = (200, 80, 220)
COLOR_TEXT = (255, 255, 255)
COLOR_HUD = (20, 20, 20)


class ViolationPipeline:
    def __init__(self, calibration_path: str, ground_point_mode: str = GROUND_POINT_MODE):
        self.detector = SchoolZoneDetector()
        self.speed_estimator = SpeedEstimator(calibration_path)
        self.crossing_monitor = CrossingMonitor(calibration_path)
        self.ground_point_mode = ground_point_mode

    def run(
        self,
        input_path: str,
        output_video_path=None,
        show_preview=False,
        frame_callback=None,
        progress_callback=None,
        stop_requested=None,
    ):
        """
        frame_callback(frame, stats: dict) -- called every frame with the
            annotated frame (BGR ndarray) and a stats dict (currently
            includes at least "frame_index"; callers should treat unknown
            keys as forward-compatible additions).
        progress_callback(current: int, total: int | None) -- called every
            frame with the current frame index and total frame count
            (None if the video's frame count is unknown).
        stop_requested() -> bool -- polled every frame; if it returns True,
            processing stops early and the returned result dict includes
            "cancelled": True.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        os.makedirs(PROCESSED_DIR, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_video_path = output_video_path or os.path.join(PROCESSED_DIR, f"{base_name}_week6_violations.mp4")

        violation_snapshot_dir = os.path.join(VIOLATIONS_DIR, base_name)
        violation_detector = ViolationDetector(violation_snapshot_dir)

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise IOError(f"Could not open video: {input_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

        tracker = SchoolZoneTracker(frame_rate=int(fps))
        counter = VehicleCounter()
        box_smoother = BoxSmoother()
        frame_index = 0
        cancelled = False

        print(f"[Violations] Processing '{input_path}' -> '{output_video_path}'")
        print(f"[Violations] Speed limit: {SPEED_LIMIT_KMH} km/h (Ghana L.I. 2180 school-zone limit)")
        progress = tqdm(total=total_frames, unit="frame", desc="Detecting violations", dynamic_ncols=True)

        while True:
            if stop_requested is not None and stop_requested():
                cancelled = True
                break

            ret, frame = cap.read()
            if not ret:
                break
            timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            results = self.detector.model.predict(
                frame, conf=self.detector.confidence, iou=self.detector.iou,
                classes=self.detector.target_class_ids, verbose=False,
            )[0]

            boxes_xyxy = [box.xyxy[0].tolist() for box in results.boxes]
            confidences = [float(box.conf[0]) for box in results.boxes]
            class_ids = [int(box.cls[0]) for box in results.boxes]

            tracked = tracker.update(boxes_xyxy, confidences, class_ids)

            frame_detections = []
            active_ids = set()
            for i in range(len(tracked)):
                raw_x1, raw_y1, raw_x2, raw_y2 = tracked.xyxy[i].tolist()
                class_id = int(tracked.class_id[i])
                confidence = float(tracked.confidence[i])
                track_id = int(tracked.tracker_id[i]) if tracked.tracker_id is not None else -1

                if track_id >= 0:
                    x1, y1, x2, y2 = box_smoother.update(track_id, (raw_x1, raw_y1, raw_x2, raw_y2))
                    active_ids.add(track_id)
                else:
                    x1, y1, x2, y2 = raw_x1, raw_y1, raw_x2, raw_y2

                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                ground_x, ground_y = (cx, y2) if self.ground_point_mode == "bottom" else (cx, cy)

                track_class = self.detector._classify(class_id)
                label = self.detector.class_map.get(class_id, "unknown")

                speed_kmh = None
                if track_class == "vehicle" and track_id >= 0:
                    speed_kmh = self.speed_estimator.update(track_id, timestamp_sec, ground_x, ground_y)

                frame_detections.append(Detection(
                    frame_index=frame_index, timestamp_sec=round(timestamp_sec, 3),
                    track_class=track_class, label=label, confidence=round(confidence, 3),
                    x1=round(x1, 1), y1=round(y1, 1), x2=round(x2, 1), y2=round(y2, 1),
                    cx=round(cx, 1), cy=round(cy, 1), track_id=track_id,
                    speed_kmh=speed_kmh,
                ))

            box_smoother.cleanup(active_ids)
            self.speed_estimator.cleanup(active_ids)
            frame_detections = pair_riders(frame_detections)
            counter.update(frame_detections)

            # Week 6: speeding violations
            violation_detector.update(frame, frame_detections)

            # Week 7: failure-to-yield violations
            pedestrian_present = self.crossing_monitor.any_pedestrian_present(frame_detections)
            for det in frame_detections:
                violation_detector.check_yield_violation(frame, det, pedestrian_present, self.crossing_monitor)
            frame = self.crossing_monitor.draw_zones(frame)

            for det in frame_detections:
                is_violating = (
                    det.track_id in violation_detector._already_flagged
                    if det.track_class == "vehicle" else False
                )

                if det.is_rider:
                    color, tag = COLOR_RIDER, f"#{det.track_id} rider"
                elif det.track_class == "vehicle":
                    color = COLOR_VIOLATION if is_violating else COLOR_VEHICLE
                    speed_txt = f"{det.speed_kmh:.0f}km/h" if det.speed_kmh is not None else "..."
                    flag_txt = " VIOLATION" if is_violating else ""
                    tag = f"{speed_txt}{flag_txt}"
                else:
                    color, tag = COLOR_PEDESTRIAN, f"#{det.track_id} {det.label}"

                cv2.rectangle(frame, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), color, 2)
                cv2.putText(frame, tag, (int(det.x1), max(int(det.y1) - 8, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1, cv2.LINE_AA)

            hud_text = f"Vehicles: {counter.total_count} | Violations: {len(violation_detector.violations)} | Limit: {SPEED_LIMIT_KMH:.0f}km/h"
            cv2.rectangle(frame, (10, 10), (520, 40), COLOR_HUD, -1)
            cv2.putText(frame, hud_text, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_TEXT, 1, cv2.LINE_AA)

            writer.write(frame)
            if show_preview:
                cv2.imshow("School Zone Violations", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if frame_callback is not None:
                stats = {
                    "frame_index": frame_index,
                    "timestamp_sec": round(timestamp_sec, 3),
                    "vehicles": counter.total_count,
                    "violations": len(violation_detector.violations),
                }
                frame_callback(frame, stats)

            if progress_callback is not None:
                progress_callback(frame_index, total_frames)

            frame_index += 1
            progress.update(1)

        progress.close()
        cap.release()
        writer.release()
        if show_preview:
            cv2.destroyAllWindows()

        json_path, csv_path = violation_detector.save_logs(base_name, PROCESSED_DIR)

        print(f"\n[Violations] Done. Frames processed: {frame_index}")
        print(f"[Violations] Annotated video: {output_video_path}")
        print(f"[Violations] Violations log: {json_path}")
        print(f"[Violations] Snapshots dir: {violation_snapshot_dir}")
        print(f"[Violations] Summary: {violation_detector.summary()}")
        if cancelled:
            print(f"[Violations] Processing cancelled by request at frame {frame_index}")

        return {
            "annotated_video": output_video_path,
            "json_log": json_path,
            "csv_log": csv_path,
            "snapshots_dir": violation_snapshot_dir,
            "summary": violation_detector.summary(),
            "cancelled": cancelled,
        }


def main():
    parser = argparse.ArgumentParser(description="School Zone violation + yield detection pipeline")
    parser.add_argument("--input", required=True)
    parser.add_argument("--calibration", default=None)
    parser.add_argument("--output-video", default=None)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--ground-point", choices=["center", "bottom"], default=None)
    args = parser.parse_args()

    calibration_path = args.calibration
    if calibration_path is None:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        calibration_path = os.path.join(CALIBRATION_DIR, f"{base_name}_calibration.json")

    pipeline = ViolationPipeline(calibration_path, ground_point_mode=args.ground_point or GROUND_POINT_MODE)
    pipeline.run(input_path=args.input, output_video_path=args.output_video, show_preview=args.preview)


if __name__ == "__main__":
    main()