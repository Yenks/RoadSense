"""
Speed estimation pipeline — Week 5, v4 (Kalman + optical flow + validation-ready logging).
"""

import os
import csv
import json
import argparse
from dataclasses import asdict

import cv2
from tqdm import tqdm

from app.config import PROCESSED_DIR, CALIBRATION_DIR, SHOW_LABEL_WITH_SPEED, GROUND_POINT_MODE
from app.detection.detector import SchoolZoneDetector, Detection
from app.detection.rider_pairing import pair_riders
from app.tracking.tracker import SchoolZoneTracker
from app.tracking.vehicle_counter import VehicleCounter
from app.tracking.box_smoother import BoxSmoother
from app.speed.speed_estimator import SpeedEstimator

COLOR_VEHICLE = (0, 140, 255)
COLOR_PEDESTRIAN = (60, 220, 60)
COLOR_RIDER = (200, 80, 220)
COLOR_TEXT = (255, 255, 255)
COLOR_HUD = (20, 20, 20)


class SpeedPipeline:
    def __init__(self, calibration_path: str, ground_point_mode: str = GROUND_POINT_MODE):
        self.detector = SchoolZoneDetector()
        self.speed_estimator = SpeedEstimator(calibration_path)
        self.ground_point_mode = ground_point_mode

    def run(self, input_path: str, output_video_path=None, output_log_path=None, show_preview=False):
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        os.makedirs(PROCESSED_DIR, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        output_video_path = output_video_path or os.path.join(PROCESSED_DIR, f"{base_name}_week5_speed.mp4")
        output_log_path = output_log_path or os.path.join(PROCESSED_DIR, f"{base_name}_week5_speed.json")
        csv_log_path = output_log_path.replace(".json", ".csv")

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
        all_detections = []
        frame_index = 0
        prev_gray = None

        print(f"[Speed] Processing '{input_path}' -> '{output_video_path}'")
        progress = tqdm(total=total_frames, unit="frame", desc="Estimating speed", dynamic_ncols=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

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
                if self.ground_point_mode == "bottom":
                    ground_x, ground_y = cx, y2
                else:
                    ground_x, ground_y = cx, cy

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
            all_detections.extend(frame_detections)

            for det in frame_detections:
                if det.is_rider:
                    color, tag = COLOR_RIDER, f"#{det.track_id} rider"
                elif det.track_class == "vehicle":
                    color = COLOR_VEHICLE
                    if det.speed_kmh is not None:
                        speed_txt = f"{det.speed_kmh:.0f}km/h"
                    else:
                        speed_txt = "..."
                    tag = f"#{det.track_id} {det.label} {speed_txt}" if SHOW_LABEL_WITH_SPEED else speed_txt
                else:
                    color, tag = COLOR_PEDESTRIAN, f"#{det.track_id} {det.label}"

                cv2.rectangle(frame, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), color, 2)
                cv2.putText(frame, tag, (int(det.x1), max(int(det.y1) - 8, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1, cv2.LINE_AA)

            hud_text = f"Vehicles counted: {counter.total_count}"
            cv2.rectangle(frame, (10, 10), (400, 40), COLOR_HUD, -1)
            cv2.putText(frame, hud_text, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_TEXT, 1, cv2.LINE_AA)

            writer.write(frame)
            if show_preview:
                cv2.imshow("School Zone Speed Estimation", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            prev_gray = curr_gray
            frame_index += 1
            progress.update(1)

        progress.close()
        cap.release()
        writer.release()
        if show_preview:
            cv2.destroyAllWindows()

        self._write_logs(all_detections, output_log_path, csv_log_path)

        print(f"[Speed] Done. Frames processed: {frame_index}")
        print(f"[Speed] Annotated video: {output_video_path}")
        print(f"[Speed] Log: {output_log_path}")

        return {"annotated_video": output_video_path, "json_log": output_log_path, "csv_log": csv_log_path}

    def _write_logs(self, detections, json_path, csv_path):
        records = []
        for d in detections:
            rec = asdict(d)
            rec["speed_confidence"] = getattr(d, "speed_confidence", None)
            records.append(rec)
        with open(json_path, "w") as jf:
            json.dump(records, jf, indent=2)
        if records:
            with open(csv_path, "w", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description="School Zone speed estimation pipeline")
    parser.add_argument("--input", required=True)
    parser.add_argument("--calibration", default=None)
    parser.add_argument("--output-video", default=None)
    parser.add_argument("--output-log", default=None)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--ground-point", choices=["center", "bottom"], default=None)
    args = parser.parse_args()

    calibration_path = args.calibration
    if calibration_path is None:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        calibration_path = os.path.join(CALIBRATION_DIR, f"{base_name}_calibration.json")

    pipeline = SpeedPipeline(calibration_path, ground_point_mode=args.ground_point or GROUND_POINT_MODE)
    pipeline.run(
        input_path=args.input,
        output_video_path=args.output_video,
        output_log_path=args.output_log,
        show_preview=args.preview,
    )


if __name__ == "__main__":
    main()