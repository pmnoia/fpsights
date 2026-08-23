# FPSights

FPSights processes recorded Valorant matches in two stages:

1. Find live-round gameplay and exclude menus, buy phases, and round-end screens.
2. Run a trained YOLO enemy detector only on those live ranges.

The processor works before YOLO training is finished. Run it without a model to
create and review the segmentation timeline, then use the same command with
`best.pt` after the CVAT dataset has been trained.

## Project structure

```text
fpsights/
├── src/
│   ├── main.py                 # One-command video processor
│   ├── segment.py              # Optional segmentation-only utility
│   └── pipeline/
│       ├── processor.py        # Segmentation + YOLO orchestration
│       ├── segmentation.py     # Valorant round/phase timeline
│       ├── detector.py         # Ultralytics YOLO adapter
│       └── frame_reader.py     # Time-range-aware frame reader
├── UI/FPSights_Pro_UI/         # Desktop UI prototype
├── docs/                       # Scope and team ownership
├── tests/
└── requirements.txt
```

Raw videos, datasets, model weights, and generated output are intentionally
ignored by Git.

See [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) for the CVAT handoff rules and the
recommended build order while footage is still being collected.

## Setup

Python 3.11 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `ffmpeg` is installed, FPSights uses it automatically for faster sampled
decoding during segmentation. OpenCV remains the built-in fallback.

## Run now: segmentation only

No YOLO model is required yet:

```bash
python -m src.main videos/vod-01.mp4
```

This writes the following files to `output/vod-01/`:

- `segments.json` — complete buy/live/round-end/non-gameplay timeline.
- `run.json` — small machine-readable run summary for future UI integration.

Only `live` intervals are copied into `analysis_ranges`. Detection and future
analytics use those ranges while keeping timestamps tied to the original VOD.

## Run after CVAT training: segmentation + YOLO

Export the CVAT annotations in Ultralytics YOLO format and train a detection
model with one initial class named `enemy`. Then point the processor at the
training run's `best.pt`:

```bash
python -m src.main videos/vod-01.mp4 \
  --model models/best.pt \
  --device mps \
  --review-video
```

The output directory will also contain:

- `detections.json` — source frame/timestamp, round, crosshair center, boxes,
  class names, and confidence values.
- `metrics.json` — crosshair score, aim-acquisition timing, and event markers
  ready for the desktop UI.
- `review.mp4` — compact live-round video with detection boxes for quick QA.

The review video contains only sampled live gameplay and has no audio. The
original VOD and JSON timestamps remain the authoritative analysis sources.
Aim-acquisition timing is the interval from first enemy detection until the
crosshair reaches the upper part of an enemy box. It is an explainable proxy;
it must not be presented as shot reaction time until shot detection is added
and validated against manually timed examples.

Useful options:

- `--confidence 0.25` changes the minimum YOLO confidence.
- `--frame-skip 5` processes every fifth live-gameplay frame.
- `--max-frames 100` runs a short pipeline smoke test.
- `--device cpu`, `--device mps`, or `--device 0` selects the inference device.
- `--preview` shows detections while processing; press `q` to stop.
- `--output-dir output/custom-name` chooses a different artifact directory.

## Reuse or correct a segmentation timeline

The automatically generated timeline is conservative. If it needs correction,
edit a copy of `segments.json` and pass it back to the processor:

```bash
python -m src.main videos/vod-01.mp4 \
  --segments output/vod-01/segments.json \
  --model models/best.pt
```

The processor validates that ranges belong to the same video, are sorted,
non-overlapping, and stay inside the source duration.

For optional per-round playback clips, the separate segmentation utility is
still available and uses `ffmpeg` stream copy:

```bash
python -m src.segment \
  --input videos/vod-01.mp4 \
  --output output/vod-01-segments.json \
  --clips-dir output/vod-01-rounds
```

## Validate the pipeline

```bash
python -m pytest -q
```

The tests exercise segmentation timelines, range-aware frame reading, YOLO
result serialization, segmentation-only processing, and the full detection +
review-video path with a local fake model.

## Launch the UI prototype

```bash
python UI/FPSights_Pro_UI/fpsights_pro_ui.py
```
