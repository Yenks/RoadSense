"""
Tracking pipeline — Week 4.

Detection (VisDrone YOLOv8m) -> ByteTrack (persistent IDs) -> rider pairing
-> vehicle counting -> annotated video + logs.

Usage:
    python -m app.tracking.pipeline --input data/raw_videos/DJI_0567_720p.mp4
"""

import os
import csv
import json
import argparse
from dataclasses import asdict

import cv2
from tqdm import tqdm

from app.config import PROCESSED_DIR
from app.detection.detector import SchoolZoneDetector, Detection
from app.detection.rider_pairing import pair_riders
from app.tracking.tracker import SchoolZoneTracker
from app.tracking.vehicle_counter import VehicleCounter

COLOR_VEHICLE = (0, 140, 255)
COLOR_PEDESTRIAN = (60, 220, 60)
COLOR_RIDER = (200, 80, 220)
COLOR_TEXT = (255, 255, 255)
COLOR_HUD = (20, 20, 20)


class TrackingPipeline:
    def __init__(self):
        self.detector = SchoolZoneDetector()

    def run(self, input_path: str, output_video_path: str = None,
             output_log_path: str = None, show_preview: bool = False):
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        os.makedirs(PROCESSED_DIR, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        output_video_path = output_video_path or os.path.join(
            PROCESSED_DIR, f"{base_name}_week4_tracked.mp4"
        )
        output_log_path = output_log_path or os.path.join(
            PROCESSED_DIR, f"{base_name}_week4_tracks.json"
        )
        counts_path = os.path.join(PROCESSED_DIR, f"{base_name}_week4_vehicle_counts.json")

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
        all_detections = []
        frame_index = 0

        print(f"[Tracking] Processing '{input_path}' -> '{output_video_path}'")
        progress = tqdm(total=total_frames, unit="frame", desc="Tracking", dynamic_ncols=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

           timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            results = self.detector.model.predict(
                frame,
                conf=self.detector.confidence,
                iou=self.detector.iou,
                classes=self.detector.target_class_ids,
                verbose=False,
            )[0]

            boxes_xyxy = [box.xyxy[0].tolist() for box in results.boxes]
            confidences = [float(box.conf[0]) for box in results.boxes]
            class_ids = [int(box.cls[0]) for box in results.boxes]

            tracked = tracker.update(boxes_xyxy, confidences, class_ids)

            frame_detections = []
            for i in range(len(tracked)):
                x1, y1, x2, y2 = tracked.xyxy[i].tolist()
                class_id = int(tracked.class_id[i])
                confidence = float(tracked.confidence[i])
                track_id = int(tracked.tracker_id[i]) if tracked.tracker_id is not None else -1
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

                track_class = self.detector._classify(class_id)
                label = self.detector.class_map.get(class_id, "unknown")

                frame_detections.append(Detection(
                    frame_index=frame_index,
                    timestamp_sec=round(timestamp_sec, 3),
                    track_class=track_class,
                    label=label,
                    confidence=round(confidence, 3),
                    x1=round(x1, 1), y1=round(y1, 1),
                    x2=round(x2, 1), y2=round(y2, 1),
                    cx=round(cx, 1), cy=round(cy, 1),
                    track_id=track_id,
                ))

            frame_detections = pair_riders(frame_detections)
            counter.update(frame_detections)
            all_detections.extend(frame_detections)

            for det in frame_detections:
                if det.is_rider:
                    color, tag = COLOR_RIDER, f"#{det.track_id} rider"
                elif det.track_class == "vehicle":
                    color, tag = COLOR_VEHICLE, f"#{det.track_id} {det.label}"
                else:
                    color, tag = COLOR_PEDESTRIAN, f"#{det.track_id} {det.label}"

                cv2.rectangle(frame, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), color, 2)
                cv2.putText(
                    frame, tag, (int(det.x1), max(int(det.y1) - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1, cv2.LINE_AA
                )

            hud_text = f"Vehicles counted: {counter.total_count}"
            cv2.rectangle(frame, (10, 10), (280, 40), COLOR_HUD, -1)
            cv2.putText(frame, hud_text, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 1, cv2.LINE_AA)

            writer.write(frame)
            if show_preview:
                cv2.imshow("School Zone Tracking", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_index += 1
            progress.update(1)

        progress.close()
        cap.release()
        writer.release()
        if show_preview:
            cv2.destroyAllWindows()

        self._write_logs(all_detections, output_log_path, csv_log_path)
        with open(counts_path, "w") as cf:
            json.dump(counter.summary(), cf, indent=2)

        print(f"[Tracking] Done. Frames processed: {frame_index}")
        print(f"[Tracking] Annotated video: {output_video_path}")
        print(f"[Tracking] Track log: {output_log_path}")
        print(f"[Tracking] Vehicle counts: {counts_path} -> {counter.summary()}")

        return {
            "annotated_video": output_video_path,
            "json_log": output_log_path,
            "csv_log": csv_log_path,
            "counts_path": counts_path,
            "counts_summary": counter.summary(),
        }

    def _write_logs(self, detections, json_path: str, csv_path: str):
        records = [asdict(d) for d in detections]
        with open(json_path, "w") as jf:
            json.dump(records, jf, indent=2)
        if records:
            with open(csv_path, "w", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description="School Zone tracking + vehicle counting")
    parser.add_argument("--input", required=True, help="Path to input video file")
    parser.add_argument("--output-video", default=None)
    parser.add_argument("--output-log", default=None)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    pipeline = TrackingPipeline()
    pipeline.run(
        input_path=args.input,
        output_video_path=args.output_video,
        output_log_path=args.output_log,
        show_preview=args.preview,
    )


if __name__ == "__main__":
    main()