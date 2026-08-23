"""Small, explainable metrics built from YOLO frame detections."""

from __future__ import annotations

from statistics import mean, median
from typing import Any


def analyze_detections(
    frames: list[dict[str, Any]],
    *,
    max_gap_ms: int = 250,
) -> dict[str, Any]:
    """Calculate crosshair and aim-acquisition metrics.

    An encounter starts when an enemy becomes visible and ends when detections
    disappear for longer than ``max_gap_ms`` or the gameplay segment changes.
    Aim acquisition means the fixed screen-center crosshair enters the upper
    35 percent of any enemy box. It is deliberately not called shot reaction
    time because shot detection is not available yet.
    """
    if max_gap_ms < 0:
        raise ValueError("max_gap_ms cannot be negative")

    scores: list[float] = []
    errors: list[float] = []
    reactions: list[int] = []
    events: list[dict[str, Any]] = []
    encounter: dict[str, Any] | None = None
    encounter_count = 0

    previous_timestamp = -1
    for frame in frames:
        timestamp_ms = _integer(frame, "timestamp_ms")
        if timestamp_ms < previous_timestamp:
            raise ValueError("detection frames must be sorted by timestamp_ms")
        previous_timestamp = timestamp_ms

        segment_id = frame.get("segment_id")
        enemies = [
            enemy
            for enemy in frame.get("enemy_positions", [])
            if _valid_box(enemy)
        ]

        if encounter is not None and (
            segment_id != encounter["segment_id"]
            or timestamp_ms - encounter["last_visible_ms"] > max_gap_ms
        ):
            encounter = None

        if not enemies:
            continue

        if encounter is None:
            encounter_count += 1
            encounter = {
                "segment_id": segment_id,
                "round_number": frame.get("round_number"),
                "start_ms": timestamp_ms,
                "last_visible_ms": timestamp_ms,
                "aligned": False,
            }
            events.append(_event("enemy_visible", frame))
        else:
            encounter["last_visible_ms"] = timestamp_ms

        crosshair_x = _integer(frame, "crosshair_x")
        crosshair_y = _integer(frame, "crosshair_y")
        error, target = min(
            (_head_error(crosshair_x, crosshair_y, enemy), enemy)
            for enemy in enemies
        )
        errors.append(error)
        scores.append(_placement_score(error, target))

        if not encounter["aligned"] and any(
            _crosshair_on_head(crosshair_x, crosshair_y, enemy)
            for enemy in enemies
        ):
            reaction_ms = timestamp_ms - encounter["start_ms"]
            encounter["aligned"] = True
            reactions.append(reaction_ms)
            events.append(
                _event("aim_acquired", frame, reaction_ms=reaction_ms)
            )

    return {
        "summary": {
            "crosshair": {
                "score_percent": _average(scores),
                "mean_head_error_px": _average(errors),
                "evaluated_frames": len(scores),
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
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"detection frame is missing integer {key}")
    return value


def _valid_box(box: Any) -> bool:
    return (
        isinstance(box, dict)
        and isinstance(box.get("x"), (int, float))
        and isinstance(box.get("y"), (int, float))
        and isinstance(box.get("w"), (int, float))
        and isinstance(box.get("h"), (int, float))
        and box["w"] > 0
        and box["h"] > 0
    )


def _head_error(crosshair_x: int, crosshair_y: int, box: dict[str, Any]) -> float:
    target_x = box["x"] + box["w"] / 2
    target_y = box["y"] + box["h"] * 0.18
    return ((crosshair_x - target_x) ** 2 + (crosshair_y - target_y) ** 2) ** 0.5


def _placement_score(error: float, box: dict[str, Any]) -> float:
    tolerance = max(1.0, box["h"] * 0.5)
    return max(0.0, 100.0 * (1.0 - error / tolerance))


def _crosshair_on_head(
    crosshair_x: int,
    crosshair_y: int,
    box: dict[str, Any],
) -> bool:
    return (
        box["x"] <= crosshair_x <= box["x"] + box["w"]
        and box["y"] <= crosshair_y <= box["y"] + box["h"] * 0.35
    )


def _event(
    event_type: str,
    frame: dict[str, Any],
    **details: Any,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "timestamp_ms": frame["timestamp_ms"],
        "round_number": frame.get("round_number"),
        "segment_id": frame.get("segment_id"),
        **details,
    }


def _average(values: list[float] | list[int]) -> float | None:
    return round(mean(values), 1) if values else None
