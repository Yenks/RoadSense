## Running Each Week

### Week 3 — Detection only
Detects and labels vehicles/pedestrians, with basic frame-to-frame
smoothing and rider-pairing heuristic.

```bash
python -m app.detection.detector --input data\raw_videos\your_video.mp4
```

Output (in `data/processed/`):
- `<name>_week3_annotated.mp4`
- `<name>_week3_detections.json` / `.csv`

---

### Week 4 — Tracking + vehicle counting
Adds ByteTrack for persistent IDs and counts vehicles once tracked.

```bash
python -m app.tracking.pipeline --input data\raw_videos\your_video.mp4
```

Output (in `data/processed/`):
- `<name>_week4_tracked.mp4`
- `<name>_week4_tracks.json` / `.csv`
- `<name>_week4_vehicle_counts.json`

---

### Week 5 — Speed estimation
Requires calibration first — **once per unique video/camera position**.
Two calibration methods are available:

**Simple (one known distance, e.g. the zebra crossing width):**
```bash
python -m app.speed.calibrate_simple --input data\raw_videos\your_video.mp4 --frame 0 --known-distance 6.65
```
A window opens — click the two endpoints of that known distance, press `q`.

**Full homography (4+ surveyed ground points, more accurate for angled/wide shots):**
```bash
python -m app.speed.calibrate --input data\raw_videos\your_video.mp4 --frame 0
```
Click each landmark, type its real-world `X,Y` in meters when prompted, press `q` when done (≥4 points).

Then run speed estimation:
```bash
python -m app.speed.pipeline --input data\raw_videos\your_video.mp4
```

Output (in `data/processed/`):
- `<name>_week5_speed.mp4` (boxes colored red if over `SPEED_LIMIT_KMH`, set in `app/config.py`)
- `<name>_week5_speed.json` / `.csv`

**Important:** calibration is per-video-filename. If you run a new clip
(e.g. `DJI_0538_720p.mp4`) that hasn't been calibrated yet, `pipeline.py`
will throw `FileNotFoundError` until you calibrate it first. Only reuse
an existing calibration file (by copying/renaming it) if you're certain
the camera position and altitude are identical between clips.

---

### Notes
- All three weeks are independently runnable — week 4/5 internally reuse
  week 3's detector class, but do not modify it, so `detector.py` (week 3)
  keeps working standalone regardless of later changes.
- `SPEED_LIMIT_KMH` in `app/config.py` is currently a placeholder (25 km/h)
  — replace with the actual posted/regulated limit for your school zone
  before treating violation counts as meaningful.


  #### (week 10 website)
cd C:\Users\Yenka\Desktop\RUIS\school-zone-safety-system
python -m app.main