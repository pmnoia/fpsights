"""Small, explainable metrics built from YOLO frame detections."""

from __future__ import annotations

from statistics import mean, median
from math import isfinite
from typing import Any

from .geometry import head_distance, estimated_head


def analyze_detections(
    frames: list[dict[str, Any]],
    *,
    max_gap_ms: int = 250,
) -> dict[str, Any]:
    """Estimate crosshair proximity and target-specific alignment time.

    Confirmed tracks prevent isolated boxes from shaping the result. Historical
    detection files without track metadata retain their original behaviour.
    """
    if max_gap_ms < 0:
        raise ValueError("max_gap_ms cannot be negative")

    scores: list[float] = []
    errors: list[float] = []
    reactions: list[int] = []
    vertical_offsets: list[float] = []
    events: list[dict[str, Any]] = []
    active: dict[int | str, dict[str, Any]] = {}
    encounter_count = 0
    previous_timestamp = -1

    for frame in frames:
        timestamp_ms = _integer(frame, "timestamp_ms")
        if timestamp_ms < previous_timestamp:
            raise ValueError("detection frames must be sorted by timestamp_ms")
        previous_timestamp = timestamp_ms
        segment_id = frame.get("segment_id")
        current_encounters = {}
        for track_id, encounter in active.items():
            same_round = encounter["segment_id"] == segment_id
            recently_seen = timestamp_ms - encounter["last_visible_ms"] <= max_gap_ms
            if same_round and recently_seen:
                current_encounters[track_id] = encounter
        active = current_encounters
        enemies = [
            enemy for enemy in frame.get("enemy_positions", [])
            if _valid_box(enemy) and enemy.get("confirmed") is not False
        ]
        if not enemies:
            continue
        crosshair_x = _integer(frame, "crosshair_x")
        crosshair_y = _integer(frame, "crosshair_y")
        target = min(
            enemies,
            key=lambda enemy: head_distance(crosshair_x, crosshair_y, enemy),
        )
        error = head_distance(crosshair_x, crosshair_y, target)
        errors.append(error)
        scores.append(_placement_score(error, target))

        # A single visible target avoids guessing which opponent the player intended.
        if len(enemies) == 1:
            vertical_offsets.append((crosshair_y - estimated_head(target)[1]) / target["h"] * 100)

        # Legacy files have no target identity: multiple enemies cannot share a timer.
        if len(enemies) > 1 and any(enemy.get("track_id") is None for enemy in enemies):
            active.pop("untracked", None)
            continue
        for enemy in enemies:
            track_id = enemy.get("track_id")
            key = track_id if track_id is not None else "untracked"
            encounter = active.get(key)
            details = {"track_id": track_id} if track_id is not None else {}
            if encounter is None:
                encounter_count += 1
                encounter = {
                    "segment_id": segment_id,
                    "start_ms": timestamp_ms,
                    "last_visible_ms": timestamp_ms,
                    "aligned": False,
                }
                active[key] = encounter
                events.append(_event("enemy_visible", frame, **details))
            else:
                encounter["last_visible_ms"] = timestamp_ms
            if not encounter["aligned"] and _crosshair_on_head(
                crosshair_x, crosshair_y, enemy
            ):
                reaction_ms = timestamp_ms - encounter["start_ms"]
                encounter["aligned"] = True
                reactions.append(reaction_ms)
                events.append(_event("aim_acquired", frame, reaction_ms=reaction_ms, **details))

    return {
        "summary": {
            "crosshair": {
                "score_percent": _average(scores),
                "mean_head_error_px": _average(errors),
                "evaluated_frames": len(scores),
            },
            "vertical_placement": {
                "mean_signed_offset_pct": _average(vertical_offsets),
                "mean_absolute_offset_pct": _average([abs(value) for value in vertical_offsets]),
                "evaluated_frames": len(vertical_offsets),
                "below_frames": sum(value > 0 for value in vertical_offsets),
                "above_frames": sum(value < 0 for value in vertical_offsets),
                "level_frames": sum(value == 0 for value in vertical_offsets),
            },
            "aim_reaction": {
                "average_ms": _average(reactions),
                "median_ms": round(median(reactions), 1) if reactions else None,
                "encounters": encounter_count,
                "measured_encounters": len(reactions),
                "unmeasured_encounters": encounter_count - len(reactions),
            },
        },
        "events": events,
    }


def _integer(payload: dict[str, Any], key: str) -> int:
    """Read a required integer field from one saved detection frame."""
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"detection frame is missing integer {key}")
    return value


def _valid_box(box: Any) -> bool:
    """Check that a detection is a usable enemy rectangle."""
    if not isinstance(box, dict) or box.get("class_name", "enemy") != "enemy":
        return False
    for key in ("x", "y", "w", "h"):
        value = box.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not isfinite(value):
            return False
    return box["w"] > 0 and box["h"] > 0


def _placement_score(error: float, box: dict[str, Any]) -> float:
    """Convert head distance into a 0 to 100 proximity estimate."""
    tolerance = max(1.0, box["h"] * 0.5)
    return max(0.0, 100.0 * (1.0 - error / tolerance))


def _crosshair_on_head(
    crosshair_x: int,
    crosshair_y: int,
    box: dict[str, Any],
) -> bool:
    """Check whether the crosshair is inside the upper 35% of a box."""
    return (
        box["x"] <= crosshair_x <= box["x"] + box["w"]
        and box["y"] <= crosshair_y <= box["y"] + box["h"] * 0.35
    )


def _event(
    event_type: str,
    frame: dict[str, Any],
    **details: Any,
) -> dict[str, Any]:
    """Create one timestamped event for the UI and saved metrics."""
    return {
        "type": event_type,
        "timestamp_ms": frame["timestamp_ms"],
        "round_number": frame.get("round_number"),
        "segment_id": frame.get("segment_id"),
        **details,
    }


def _average(values: list[float] | list[int]) -> float | None:
    """Return a rounded mean, or ``None`` when there is no data."""
    return round(mean(values), 1) if values else None
