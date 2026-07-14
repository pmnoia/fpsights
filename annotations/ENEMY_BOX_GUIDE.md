# Enemy Bounding-Box Annotation Guide

This guide defines the ground truth used to train and evaluate the FPSights
enemy detector. It complements `ANNOTATION_GUIDE.md`, which describes gameplay
events rather than per-image object-detection labels.

## Tool and export format

Use CVAT and export the task as **Ultralytics YOLO Detection**.

The dataset has one label:

```text
enemy
```

Ultralytics label files contain one row per object:

```text
class_id x_center y_center width height
```

All four coordinates are normalized to the range 0–1. `class_id` is `0`.

## Box rules

1. Box the visible enemy character as tightly as practical.
2. Include the visible outline and body.
3. When an enemy is partially occluded, box only the visible extent.
4. Keep a box when motion blur is present if the enemy remains identifiable.
5. Give each visible enemy a separate box.
6. Review boxes at native frame resolution before accepting them.

## Exclusions

Do not annotate allies, corpses, minimap icons, agent portraits, kill-feed art,
sprays, or HUD elements. Keep frames containing these items as negative examples
when no real enemy is visible.

## Quality checklist

Before export, verify that:

- the label name is exactly `enemy`;
- boxes do not extend beyond the image;
- every visible enemy follows the same occlusion rule;
- negative frames have no boxes;
- duplicate neighboring frames are limited; and
- each source video or round belongs to only one dataset split.

## Review process

One annotator labels the frames. A second team member reviews every validation
and test frame plus a sample of training frames. Disagreements are resolved
before training, and corrected exports receive a new dataset revision.
