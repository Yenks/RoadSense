# Intelligent School Zone Safety Monitoring System

A computer vision system that monitors school-zone traffic in real time —
detecting pedestrians and vehicles, tracking their movement, estimating
vehicle speed, and flagging safety violations near pedestrian crossings.

Built as an 11-week academic project using YOLOv8, ByteTrack, and Flask.

## Status

| Week | Milestone | Status |
|---|---|---|
| 1 | Requirements & literature review | Done |
| 2 | Data collection & preprocessing | Done |
| 3 | Object detection (vehicles + pedestrians) | Done |
| 4 | Object tracking + vehicle counting | Done |
| 5 | Speed estimation | Not started |
| 6 | Violation detection | Not started |
| 7 | Pedestrian conflict detection | Not started |
| 8 | Backend + database | Not started |
| 9 | Dashboard frontend | Not started |
| 10 | Testing & evaluation | Not started |
| 11 | Documentation & demo | Not started |

## Source Footage

Test footage is captured from a **fixed/hovering drone** (aerial, near
top-down view), not a roadside camera. This affects both the detection
model choice and future speed-calibration work (Week 5).

## Detection Model

Uses `mshamrai/yolov8m-visdrone` — a YOLOv8 model pretrained on
**VisDrone**, a dataset built specifically for aerial/drone imagery.
This was chosen over standard COCO-pretrained YOLOv8 because:

- COCO is trained almost entirely on ground-level photos, which performed
  poorly on aerial footage.
- VisDrone's native classes already include `tricycle` and
  `awning-tricycle` — categories COCO doesn't have at all.

Native classes: `pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor`

The model auto-downloads from Hugging Face on first run and is cached
locally in `data/models/`.

## Setup

```bash
git clone <your-repo-url>
cd school-zone-safety-system
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Place your test video in `data/raw_videos/`.

## Usage

### Week 3 — Detection only
Detects and labels vehicles/pedestrians per frame, with basic frame-to-frame
stabilization (smoothing + short-occlusion coasting) and a rider-pairing
heuristic (flags a person overlapping a bike/motor/tricycle as a rider).

```bash
python -m app.detection.detector --input data/raw_videos/your_video.mp4
```

Outputs to `data/processed/`:
- `<name>_annotated.mp4` — video with boxes drawn
- `<name>_detections.json` / `.csv` — per-frame detection log

### Week 4 — Tracking + vehicle counting
Adds ByteTrack for persistent object IDs across frames (survives brief
occlusion) and counts vehicles once their track is confirmed.

```bash
python -m app.tracking.pipeline --input data/raw_videos/your_video.mp4
```

Outputs to `data/processed/`:
- `<name>_tracked.mp4` — video with persistent track IDs drawn
- `<name>_tracks.json` / `.csv` — per-frame tracked detection log
- `<name>_vehicle_counts.json` — total vehicle count, broken down by type

Both commands run independently — Week 4 reuses Week 3's detector code
internally but does not modify it, so Week 3 remains fully testable on
its own.

## Project Structure
