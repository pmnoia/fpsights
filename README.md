# FPSights
## Desktop FPS VOD Analysis & Coaching Assistant

FPSights is a desktop application that analyzes recorded FPS gameplay videos (VODs) and generates automated post-match coaching reports. It uses computer vision to measure crosshair placement, reaction time, and player positioning, then provides actionable insights for improvement.

### Features (MVP)
- Crosshair placement tracking and alignment scoring
- Reaction time estimation from enemy encounters
- Player positioning heatmap with kill/death markers
- Automated post-match report (in-app + PDF export)

### Enemy Detection Direction

Enemy detection supports the original FPSights reaction-time and crosshair
features. It uses one custom YOLO model on recorded video and outputs enemy
boxes for the analytics pipeline. The original MVP remains defined by
`docs/SCOPE.md`; `docs/ENEMY_DETECTION_STRATEGY.md` explains this component.

Initialize a local dataset and sample one frame per second from a recording:

```bash
python -m src.dataset.prepare_enemy_dataset init --root data/enemy_detection
python -m src.dataset.prepare_enemy_dataset extract \
  --root data/enemy_detection \
  --video /path/to/recorded-match.mp4 \
  --interval-seconds 1
```

Extracted images are written to `raw/images`, with exact source-frame metadata
recorded in `sampling_manifest.csv`. Annotate those images using
`annotations/ENEMY_BOX_GUIDE.md` before assigning complete videos or rounds to
the train, validation, and test directories.

The runtime code has two small interfaces:

```python
from src.analysis import EnemyDetector, ReactionTimeCalculator

detector = EnemyDetector("path/to/best.pt")
reaction = ReactionTimeCalculator()

detections = detector.detect(frame)
event = reaction.update(timestamp_ms, detections, (frame_width, frame_height))
```

`event` is returned when the first sustained aim correction is detected, or
when an encounter ends without a measurable response.

Train one small model after the frames have been annotated and split:

```bash
yolo detect train \
  model=yolo11n.pt \
  data=data/enemy_detection/data.yaml \
  epochs=50 \
  imgsz=640
```

After training, run the MVP analysis on a recorded video:

```bash
python -m src.analysis.analyze_video \
  --video /path/to/recorded-match.mp4 \
  --model /path/to/best.pt \
  --output data/output/reactions.json
```

On CPU, add `--batch-size 8` to run inference in small batches while still
processing every video frame in timestamp order. Use `--confidence` to apply a
threshold calibrated on the held-out test split; the default is `0.25`.

The JSON contains video metadata and reaction events only.

### Tech Stack
- **Language:** Python 3.11+
- **Desktop UI:** PySide6
- **Computer Vision:** OpenCV (+ optional YOLO)
- **Database:** SQLite
- **Reporting:** Matplotlib + ReportLab / HTML-to-PDF

## Repository Structure
```text
fpsights/
├── UI/FPSights_Pro_UI/        
│   └── fpsights_pro_ui.py
├── src/                       
│   ├── main.py
│   └── utils/config.py
├── docs/
├── annotations/
├── maps/
├── requirements.txt
└── README.md
```

## Project Setup
Run these commands from the `fpsights` folder.

```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Launch UI Prototype
```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
source venv/bin/activate
python UI/FPSights_Pro_UI/fpsights_pro_ui.py
```

## Launch Current App Entry (non-UI stub)
```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
source venv/bin/activate
python src/main.py
```

## Annotation Assets
- Schema guide: `annotations/ANNOTATION_GUIDE.md`
- Sample labels: `annotations/vod_001_sample.csv`

## Common Issues
- **`ModuleNotFoundError: PySide6`**  
  Make sure venv is activated and reinstall dependencies:
  `pip install -r requirements.txt`
- **UI does not open on macOS**  
  Run the script directly (not from a restricted environment), and verify Python is from `venv/bin/python`.
