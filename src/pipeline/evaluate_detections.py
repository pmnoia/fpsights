import argparse
import csv
import json
import statistics


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate FPSights detections against manual annotations.")
    parser.add_argument("--detections", required=True, help="JSON file produced by video_to_json.py")
    parser.add_argument("--annotations", required=True, help="CSV file following annotations/ANNOTATION_GUIDE.md")
    parser.add_argument("--event-tolerance-ms", type=float, default=250.0)
    parser.add_argument("--iou-threshold", type=float, default=0.3)
    parser.add_argument("--output", default=None, help="Optional path to write metrics JSON")
    args = parser.parse_args()

    if args.event_tolerance_ms < 0:
        parser.error("--event-tolerance-ms cannot be negative")
    if not 0 <= args.iou_threshold <= 1:
        parser.error("--iou-threshold must be between 0 and 1")

    return args


def load_detections(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_annotations(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def number_or_none(value):
    if value is None or value == "":
        return None
    return float(value)


def annotation_bbox(row):
    x = number_or_none(row.get("enemy_bbox_x"))
    y = number_or_none(row.get("enemy_bbox_y"))
    w = number_or_none(row.get("enemy_bbox_w"))
    h = number_or_none(row.get("enemy_bbox_h"))

    if None in (x, y, w, h):
        return None

    return {"x": x, "y": y, "w": w, "h": h}


def iou(a, b):
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    area_a = max(0.0, a["w"]) * max(0.0, a["h"])
    area_b = max(0.0, b["w"]) * max(0.0, b["h"])
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0
    return intersection / union


def f1(precision, recall):
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_enemy_visible_events(detections_json, annotations, tolerance_ms):
    gt_events = [
        {
            "frame_number": int(float(row["frame_number"])),
            "timestamp_ms": float(row["timestamp_ms"]),
        }
        for row in annotations
        if row.get("event_type") == "enemy_visible"
    ]
    pred_events = [
        {
            "frame_number": int(event["frame_number"]),
            "timestamp_ms": float(event["timestamp_ms"]),
        }
        for event in detections_json.get("events", [])
        if event.get("type") == "enemy_visible"
    ]

    unmatched_pred_indexes = set(range(len(pred_events)))
    matches = []

    for gt in gt_events:
        best_index = None
        best_delta = None

        for pred_index in unmatched_pred_indexes:
            pred = pred_events[pred_index]
            delta = abs(pred["timestamp_ms"] - gt["timestamp_ms"])
            if delta <= tolerance_ms and (best_delta is None or delta < best_delta):
                best_index = pred_index
                best_delta = delta

        if best_index is not None:
            unmatched_pred_indexes.remove(best_index)
            pred = pred_events[best_index]
            matches.append({
                "gt_frame": gt["frame_number"],
                "pred_frame": pred["frame_number"],
                "gt_timestamp_ms": gt["timestamp_ms"],
                "pred_timestamp_ms": pred["timestamp_ms"],
                "timing_error_ms": pred["timestamp_ms"] - gt["timestamp_ms"],
            })

    true_positive = len(matches)
    false_positive = len(pred_events) - true_positive
    false_negative = len(gt_events) - true_positive
    precision = true_positive / len(pred_events) if pred_events else 0.0
    recall = true_positive / len(gt_events) if gt_events else 0.0
    timing_abs_errors = [abs(match["timing_error_ms"]) for match in matches]

    return {
        "ground_truth_events": len(gt_events),
        "predicted_events": len(pred_events),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
        "mean_abs_timing_error_ms": statistics.mean(timing_abs_errors) if timing_abs_errors else None,
        "max_abs_timing_error_ms": max(timing_abs_errors) if timing_abs_errors else None,
        "matches": matches,
    }


def evaluate_labeled_bbox_frames(detections_json, annotations, iou_threshold):
    frames_by_number = {
        int(frame["frame_number"]): frame
        for frame in detections_json.get("frames", [])
    }
    annotated_boxes = []

    for row in annotations:
        bbox = annotation_bbox(row)
        if bbox is None:
            continue

        annotated_boxes.append({
            "frame_number": int(float(row["frame_number"])),
            "timestamp_ms": float(row["timestamp_ms"]),
            "bbox": bbox,
            "event_type": row.get("event_type"),
        })

    hits = []
    misses = []
    best_ious = []

    for gt in annotated_boxes:
        frame = frames_by_number.get(gt["frame_number"])
        boxes = frame.get("enemy_positions", []) if frame else []
        best_iou = max((iou(gt["bbox"], box) for box in boxes), default=0.0)
        best_ious.append(best_iou)

        result = {
            "frame_number": gt["frame_number"],
            "timestamp_ms": gt["timestamp_ms"],
            "event_type": gt["event_type"],
            "best_iou": best_iou,
            "detections_on_frame": len(boxes),
        }

        if best_iou >= iou_threshold:
            hits.append(result)
        else:
            result["reason"] = "missing_frame" if frame is None else "low_iou_or_no_detection"
            misses.append(result)

    recall = len(hits) / len(annotated_boxes) if annotated_boxes else 0.0

    return {
        "labeled_bbox_frames": len(annotated_boxes),
        "hits": len(hits),
        "misses": len(misses),
        "bbox_recall_on_labeled_frames": recall,
        "mean_best_iou": statistics.mean(best_ious) if best_ious else None,
        "miss_details": misses,
    }


def print_metrics(metrics):
    run = metrics["run"]
    events = metrics["enemy_visible_events"]
    bbox = metrics["labeled_bbox_frames"]

    print("--------FPSights Detection Evaluation---------")
    print(f"Input JSON:       {run.get('detections_path')}")
    print(f"Annotations CSV:  {run.get('annotations_path')}")
    print(f"Frame skip:       {run.get('frame_skip')}")
    print(f"Method:           {run.get('method')} / {run.get('highlight_color')}")
    print("")
    print("Enemy-visible events")
    print(f"  GT events:      {events['ground_truth_events']}")
    print(f"  Pred events:    {events['predicted_events']}")
    print(f"  TP / FP / FN:   {events['true_positive']} / {events['false_positive']} / {events['false_negative']}")
    print(f"  Precision:      {events['precision']:.3f}")
    print(f"  Recall:         {events['recall']:.3f}")
    print(f"  F1:             {events['f1']:.3f}")
    if events["mean_abs_timing_error_ms"] is not None:
        print(f"  Mean abs error: {events['mean_abs_timing_error_ms']:.1f} ms")
        print(f"  Max abs error:  {events['max_abs_timing_error_ms']:.1f} ms")
    print("")
    print("Labeled bbox frames")
    print(f"  Labeled frames: {bbox['labeled_bbox_frames']}")
    print(f"  Hits / misses:  {bbox['hits']} / {bbox['misses']}")
    print(f"  Bbox recall:    {bbox['bbox_recall_on_labeled_frames']:.3f}")
    if bbox["mean_best_iou"] is not None:
        print(f"  Mean best IoU:  {bbox['mean_best_iou']:.3f}")

    if bbox["miss_details"]:
        print("")
        print("First bbox misses")
        for miss in bbox["miss_details"][:10]:
            print(
                f"  frame={miss['frame_number']} event={miss['event_type']} "
                f"best_iou={miss['best_iou']:.3f} detections={miss['detections_on_frame']} "
                f"reason={miss['reason']}"
            )


def main():
    args = parse_args()
    detections_json = load_detections(args.detections)
    annotations = load_annotations(args.annotations)

    metrics = {
        "run": {
            **detections_json.get("run", {}),
            "detections_path": args.detections,
            "annotations_path": args.annotations,
            "event_tolerance_ms": args.event_tolerance_ms,
            "iou_threshold": args.iou_threshold,
            "evaluation_note": (
                "This CSV labels event frames, not every video frame. Event precision is based on "
                "predicted enemy_visible events; bbox recall is based only on annotated positive frames."
            ),
        },
        "enemy_visible_events": evaluate_enemy_visible_events(
            detections_json,
            annotations,
            args.event_tolerance_ms,
        ),
        "labeled_bbox_frames": evaluate_labeled_bbox_frames(
            detections_json,
            annotations,
            args.iou_threshold,
        ),
    }

    print_metrics(metrics)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
            f.write("\n")
        print("")
        print(f"Wrote metrics JSON -> {args.output}")


if __name__ == "__main__":
    main()
