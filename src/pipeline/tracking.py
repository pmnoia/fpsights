"""Associate sampled enemy boxes across adjacent video frames."""

from __future__ import annotations

from typing import Any

from .geometry import box_overlap


def confirm_tracks(
    frames: list[dict[str, Any]], *, max_gap_ms: int = 250
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Mark boxes confirmed after two matching observations in one live segment.

    This is a small offline association step, not a learned tracker. Raw boxes
    remain available for review, while metrics can ignore isolated predictions.
    """
    if max_gap_ms < 0:
        raise ValueError("max_gap_ms cannot be negative")
    # Copy the input so adding track IDs cannot change the saved raw detections.
    output = []
    for frame in frames:
        boxes = []
        for box in frame.get("enemy_positions", []):
            boxes.append({**box, "track_id": None, "confirmed": False})
        output.append({**frame, "enemy_positions": boxes})
    active: dict[int, tuple[str | None, int, dict[str, Any]]] = {}
    observations: dict[int, list[dict[str, Any]]] = {}
    next_id = 1

    for frame in output:
        timestamp = frame["timestamp_ms"]
        segment = frame.get("segment_id")
        # Old tracks cannot be matched after a new round or a long gap.
        still_active = {}
        for track_id, state in active.items():
            same_round = state[0] == segment
            close_in_time = 0 <= timestamp - state[1] <= max_gap_ms
            if same_round and close_in_time:
                still_active[track_id] = state
        active = still_active
        boxes = frame["enemy_positions"]
        possible = []
        for track_id, (_, _, previous_box) in active.items():
            for index, box in enumerate(boxes):
                if box.get("class_name") == "enemy":
                    overlap = box_overlap(previous_box, box)
                    possible.append((overlap, track_id, index))
        possible.sort(reverse=True)
        used_tracks: set[int] = set()
        used_boxes: set[int] = set()
        for overlap, track_id, index in possible:
            if overlap < 0.2:
                break
            if track_id in used_tracks or index in used_boxes:
                continue
            used_tracks.add(track_id)
            used_boxes.add(index)
            box = boxes[index]
            box["track_id"] = track_id
            active[track_id] = (segment, timestamp, box)
            observations[track_id].append(box)

        for index, box in enumerate(boxes):
            if index in used_boxes or box.get("class_name") != "enemy":
                continue
            track_id = next_id
            next_id += 1
            box["track_id"] = track_id
            active[track_id] = (segment, timestamp, box)
            observations[track_id] = [box]

    confirmed_tracks = 0
    confirmed_boxes = 0
    for boxes in observations.values():
        if len(boxes) >= 2:
            confirmed_tracks += 1
            confirmed_boxes += len(boxes)
            for box in boxes:
                box["confirmed"] = True
    isolated_boxes = sum(len(boxes) == 1 for boxes in observations.values())
    return output, {
        "tracks": len(observations),
        "confirmed_tracks": confirmed_tracks,
        "confirmed_boxes": confirmed_boxes,
        "isolated_boxes": isolated_boxes,
    }

