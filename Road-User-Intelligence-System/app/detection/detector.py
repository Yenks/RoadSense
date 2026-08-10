"""
Detection module — Week 3, upgraded to a VisDrone-trained model (aerial-native,
includes tricycle/awning-tricycle classes) with rider pairing and a live
progress bar.

Usage (CLI):
    python -m app.detection.detector --input data/raw_videos/DJI_0567_720p.mp4
"""

import os
import csv
import json
import argparse
from dataclasses import dataclass, asdict, field

import cv2
from tqdm import tqdm
from ultralytics import YOLO
from huggingface_hub import hf_hub_download

from app.config import (
    MODELS_DIR,
    PROCESSED_DIR,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    VEHICLE_CLASSES,
    PEDESTRIAN_CLASS,
    HF_REPO_ID,
    HF_WEIGHTS_FILENAME,
    LOCAL_MODEL_FILENAME,
)
from app.detection.stabilizer import DetectionStabilizer
from app.detection.rider_pairing import pair_riders

COLOR_VEHICLE = (0, 140, 255)     # orange
COLOR_PEDESTRIAN = (60, 220, 60)  # green
COLOR_RIDER = (200, 80, 220)      # magenta/purple — distinct from plain pedestrian
COLOR_TEXT = (255, 255, 255)


@dataclass
class Detection:
    frame_index: int
    timestamp_sec: float
    track_class: str        # "vehicle" or "pedestrian"
    label: str               # e.g. "car", "motor", "tricycle", "pedestrian"
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    cx: float
    cy: float
    track_id: int = field(default=-1)
    is_rider: bool = field(default=False)   # True if this person overlaps a rideable vehicle
    speed_kmh: float = field(default=None)  # populated in Week 5, None in Week 3/4 runs


class SchoolZoneDetector:
    def __init__(self, model_path: str = None, confidence: float = CONFIDENCE_THRESHOLD,
                 iou: float = IOU_THRESHOLD):
        self.model_path = model_path or self._resolve_model_path()
        self.confidence = confidence
        self.iou = iou
        self.model = YOLO(self.model_path)

        self.class_map = {**VEHICLE_CLASSES, **PEDESTRIAN_CLASS}
        self.target_class_ids = list(self.class_map.keys())

    def _resolve_model_path(self) -> str:
        os.makedirs(MODELS_DIR, exist_ok=True)
        local_path = os.path.join(MODELS_DIR, LOCAL_MODEL_FILENAME)
        if os.path.exists(local_path):
            return local_path

        print(f"[Detector] Downloading {HF_REPO_ID} (first run only, may take a minute)...")
        downloaded_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_WEIGHTS_FILENAME)

        # Cache a copy locally so we don't re-download every run
        import shutil
        shutil.copy(downloaded_path, local_path)
        return local_path

    def _classify(self, class_id: int) -> str:
        if class_id in VEHICLE_CLASSES:
            return "vehicle"
        if class_id in PEDESTRIAN_CLASS:
            return "pedestrian"
        return "other"

    def run(self, input_path: str, output_video_path: str = None,
             output_log_path: str = None, show_preview: bool = False):
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        os.makedirs(PROCESSED_DIR, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        output_video_path = output_video_path or os.path.join(
            PROCESSED_DIR, f"{base_name}_week3_annotated.mp4"
        )
        output_log_path = output_log_path or os.path.join(
            PROCESSED_DIR, f"{base_name}_week3_detections.json"
        )
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

        stabilizer = DetectionStabilizer()
        all_detections = []
        frame_index = 0

        print(f"[Detector] Processing '{input_path}' -> '{output_video_path}'")
        progress = tqdm(total=total_frames, unit="frame", desc="Detecting", dynamic_ncols=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_sec = frame_index / fps

            results = self.model.predict(
                frame,
                conf=self.confidence,
                iou=self.iou,
                classes=self.target_class_ids,
                verbose=False,
            )[0]

            raw_detections = []
            for box in results.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                track_class = self._classify(class_id)
                label = self.class_map.get(class_id, "unknown")

                raw_detections.append(Detection(
                    frame_index=frame_index,
                    timestamp_sec=round(timestamp_sec, 3),
                    track_class=track_class,
                    label=label,
                    confidence=round(confidence, 3),
                    x1=round(x1, 1), y1=round(y1, 1),
                    x2=round(x2, 1), y2=round(y2, 1),
                    cx=round(cx, 1), cy=round(cy, 1),
                ))

            # Tag riders (person overlapping a bike/motor/tricycle) before stabilizing
            raw_detections = pair_riders(raw_detections)

            stable_detections = stabilizer.update(raw_detections)
            all_detections.extend(stable_detections)

            for det in stable_detections:
                if det.is_rider:
                    color = COLOR_RIDER
                    tag = f"#{det.track_id} rider"
                elif det.track_class == "vehicle":
                    color = COLOR_VEHICLE
                    tag = f"#{det.track_id} {det.label} {det.confidence:.2f}"
                else:
                    color = COLOR_PEDESTRIAN
                    tag = f"#{det.track_id} {det.label} {det.confidence:.2f}"

                cv2.rectangle(
                    frame, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), color, 2
                )
                cv2.putText(
                    frame, tag,
                    (int(det.x1), max(int(det.y1) - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1, cv2.LINE_AA
                )

            writer.write(frame)
            if show_preview:
                cv2.imshow("School Zone Detector", frame)
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

        print(f"[Detector] Done. Frames processed: {frame_index}")
        print(f"[Detector] Annotated video: {output_video_path}")
        print(f"[Detector] JSON log: {output_log_path}")
        print(f"[Detector] CSV log:  {csv_log_path}")

        return {
            "annotated_video": output_video_path,
            "json_log": output_log_path,
            "csv_log": csv_log_path,
            "num_detections": len(all_detections),
            "num_frames": frame_index,
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
    parser = argparse.ArgumentParser(description="School Zone vehicle/pedestrian detector")
    parser.add_argument("--input", required=True, help="Path to input video file")
    parser.add_argument("--output-video", default=None, help="Path for annotated output video")
    parser.add_argument("--output-log", default=None, help="Path for JSON detection log")
    parser.add_argument("--preview", action="store_true", help="Show live preview window")
    args = parser.parse_args()

    detector = SchoolZoneDetector()
    detector.run(
        input_path=args.input,
        output_video_path=args.output_video,
        output_log_path=args.output_log,
        show_preview=args.preview,
    )


if __name__ == "__main__":
    main()