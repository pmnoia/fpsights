# Enemy Detection Component

## Source of truth

`docs/SCOPE.md` defines the FPSights MVP:

1. crosshair placement tracking;
2. reaction-time estimation;
3. player-positioning heatmap; and
4. automated post-match reporting.

Enemy detection is one supporting component. This document does not replace or
reduce the original project scope.

## Responsibility of this component

For a recorded gameplay video, this component will:

1. detect visible enemies with one custom YOLO model;
2. mark when an enemy first becomes visible; and
3. provide the enemy-box data needed to calculate reaction time.

The output will later feed the crosshair and reporting parts of FPSights.

## What to reuse from the reference

The linked [computer-vision video](https://www.youtube.com/watch?v=LXA7zXVz8A4)
is a reference, not an implementation specification.

Use only:

- object detection on gameplay frames;
- a custom labeled dataset; and
- enemy bounding boxes with confidence scores.

Do not copy features that FPSights does not need:

- R-CNN as a second detector;
- aim or input control;
- a live overlay;
- game-memory or network access; or
- real-time competitive assistance.

FPSights processes recorded videos after gameplay.

## Minimal detection pipeline

```text
recorded video -> frames -> YOLO -> enemy boxes -> FPSights analytics
```

YOLO returns this data for each visible enemy:

```text
Detection
  box: (x_min, y_min, x_max, y_max)
  confidence: 0.0 to 1.0
```

The first model has one class:

```text
0: enemy
```

## Reaction time

The original scope defines reaction time as the delay from enemy appearance to
the player's first aim correction or shot:

```text
reaction_time_ms = response_timestamp_ms - enemy_visible_timestamp_ms
```

- `enemy_visible_timestamp_ms`: first frame where YOLO detects the enemy
- `response_timestamp_ms`: first detected aim correction or shot after the
  enemy appears

The first implementation should use the simplest response signal that can meet
the existing `<= 100 ms` error target. A practical first signal is the start of
a sustained decrease in the distance between the screen-center crosshair and
the enemy box. A shot signal should be added only if evaluation shows it is
needed.

Manual labels in `annotations/ANNOTATION_GUIDE.md` remain the ground truth for
`enemy_visible`, `aim_correction_start`, and `shot_fired`.

## Dataset

Use CVAT and export **Ultralytics YOLO Detection** labels. Follow
`annotations/ENEMY_BOX_GUIDE.md`.

Start with:

- 100–300 labeled enemy examples;
- negative frames containing HUD, abilities, allies, and no enemy; and
- train, validation, and test splits separated by complete video or round.

Do not randomly split neighboring frames because they are nearly identical.

## Existing acceptance criteria

| Metric | Target |
|---|---:|
| Enemy precision | >= 0.70 |
| Enemy recall | >= 0.65 |
| Reaction-time error vs manual labels | <= 100 ms |

## Build steps

1. Sample frames and annotate `enemy` boxes.
2. Train one small YOLO model.
3. Add a small `detect(frame)` adapter.
4. Convert detections into `enemy_visible` events.
5. Calculate reaction time from the first response signal.
6. Compare results with the manual annotations.
7. Connect the results to the original FPSights report pipeline.

Add another model, tracker, or signal only when evaluation proves the simple
version cannot meet an MVP target.

## Required reading

- [FPSights scope](SCOPE.md)
- [Ultralytics detection datasets](https://docs.ultralytics.com/datasets/detect/)
- [Ultralytics object detection](https://docs.ultralytics.com/tasks/detect/)
- [Ultralytics Python usage](https://docs.ultralytics.com/usage/python/)
- [Ultralytics validation metrics](https://docs.ultralytics.com/guides/yolo-performance-metrics/)
- [CVAT Ultralytics YOLO format](https://docs.cvat.ai/docs/dataset_management/formats/format-yolo-ultralytics/)
- [Riot Games Terms of Service](https://www.riotgames.com/en/terms-of-service-update-2024)
