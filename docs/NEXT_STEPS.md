# FPSights — Next Steps

## What already works

- Gameplay/buy/round-end segmentation without a trained model
- YOLO inference restricted to live-round ranges
- Detection, review-video, and run artifacts
- Crosshair score, aim-acquisition timing, and UI-ready event artifacts
- Automated tests using generated videos and fake detections

## Footage and CVAT handoff

Provide the original VODs plus a CVAT **Ultralytics YOLO Detection** export.
For the first model, use exactly one class named `enemy`.

Annotation rules:

- Draw one tight box around every visible enemy body.
- Include partially visible enemies when a person is still identifiable.
- Do not label teammates, corpses, portraits, minimap icons, or UI artwork.
- Keep the source video name with each exported image or task.
- Split train/validation/test by source VOD, not by random frames. Adjacent
  frames are too similar and would make validation results look falsely good.

Edited replay compilations are valid CVAT sources, even when one file contains
highlights from several matches. Keep the entire compilation—and any source
VODs it was cut from—in one dataset split. Label only first-person gameplay that
matches FPSights' real input, and avoid repeated or slow-motion copies of the
same moment. Use unrelated full VODs for validation and testing so model quality
is measured on the app's actual single-match workflow.

Aim for several VODs covering different maps, agents, enemy distances, visual
effects, and both supported resolutions. A single VOD is enough to prove the
workflow, but not enough to judge model quality.

## Build order

1. **Now — pipeline contract:** Finish segmentation, metrics JSON, event JSON,
   failure messages, and tests. Use synthetic detections until weights arrive.
2. **Next — desktop integration:** Let the UI select a VOD, run processing in a
   worker thread, and render real values from `run.json` and `metrics.json`.
3. **When CVAT arrives — model loop:** Validate the export, create VOD-level
   splits, train a small YOLO model, and review false positives/negatives on a
   held-out VOD.
4. **After detection is stable — calibration:** Compare crosshair and
   aim-acquisition metrics with manually timed examples and tune thresholds.
5. **Then — minimap and reporting:** Add player-map localization, SQLite match
   history, coaching rules, and PDF export in that order.

Do not call aim acquisition "shot reaction time" yet. True shot reaction needs
a separate shot signal (audio, muzzle flash, or ammo-change detection) and
manual timing labels. Do not start generalized coaching recommendations until
the underlying metrics have been validated.

## Definition of the next milestone

The next milestone is complete when a user can choose one VOD in the desktop
app, process it without a crash, and see real segmentation and metric results.
A YOLO model may be optional for this milestone; the UI should explain when
detection-dependent metrics are unavailable.
