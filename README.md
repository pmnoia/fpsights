# FPSights

FPSights is a desktop FPS VOD analysis project. Enemy detection uses a trained
YOLO model; color/HSV thresholding is no longer part of the pipeline.

The current goal is intentionally narrow: collect reliable CVAT annotations,
train YOLO, and run repeatable inference on recorded gameplay. The existing UI
and minimap assets remain available for later integration.

## Repository structure

```text
fpsights/
├── src/
│   ├── main.py                 # Video inference CLI
│   └── pipeline/
│       ├── detector.py         # YOLO adapter
│       └── frame_reader.py     # Video frame iterator
├── UI/FPSights_Pro_UI/         # Desktop UI prototype
├── maps/                       # Minimap assets for future heatmaps
├── docs/                       # Scope and team ownership
├── requirements.txt
└── README.md
```

Raw videos, screenshots, CVAT exports, model weights, training runs, and
generated outputs are local-only and ignored by Git.

## Setup

Python 3.11 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run YOLO inference

Use weights trained on the CVAT-exported enemy class:

```bash
python -m src.main \
  --input videos/vod-01.mp4 \
  --model models/best.pt \
  --output output/vod-01.json
```

Useful options:

- `--confidence 0.25` sets the minimum prediction confidence.
- `--frame-skip 5` processes every fifth frame.
- `--max-frames 100` limits a quick test run.
- `--device mps` selects Apple Silicon acceleration when supported.
- `--preview` opens a live preview; press `q` to stop.

The pipeline assumes every class produced by the custom model is a relevant
enemy class. Keep the first dataset simple with one class named `enemy`.

## Dataset workflow

Export annotations from CVAT in Ultralytics YOLO format and keep them under a
local `datasets/` directory. One annotated recording is enough to validate the
workflow, but not enough to judge generalization. Add recordings with different
maps, agents, lighting/effects, resolutions, and enemy distances before relying
on model metrics.

## Launch the UI prototype

```bash
python UI/FPSights_Pro_UI/fpsights_pro_ui.py
```
