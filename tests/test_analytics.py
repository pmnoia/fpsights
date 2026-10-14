from __future__ import annotations

import pytest

from src.pipeline.analytics import analyze_detections


def _frame(
    timestamp_ms: int,
    crosshair: tuple[int, int],
    *,
    enemies: list[dict] | None = None,
    segment_id: str = "round-1",
) -> dict:
    return {
        "timestamp_ms": timestamp_ms,
        "segment_id": segment_id,
        "round_number": 1,
        "crosshair_x": crosshair[0],
        "crosshair_y": crosshair[1],
        "enemy_positions": enemies or [],
    }


ENEMY = {"x": 100, "y": 100, "w": 100, "h": 200}


def test_calculates_aim_acquisition_and_ui_events() -> None:
    result = analyze_detections(
        [
            _frame(0, (20, 300), enemies=[ENEMY]),
            _frame(100, (150, 136), enemies=[ENEMY]),
            _frame(200, (150, 136)),
            _frame(500, (150, 120), enemies=[ENEMY]),
        ]
    )

    reaction = result["summary"]["aim_reaction"]
    assert reaction == {
        "average_ms": 50,
        "median_ms": 50.0,
        "encounters": 2,
        "measured_encounters": 2,
        "unmeasured_encounters": 0,
    }
    assert [event["type"] for event in result["events"]] == [
        "enemy_visible",
        "aim_acquired",
        "enemy_visible",
        "aim_acquired",
    ]
    assert result["events"][1]["reaction_ms"] == 100


def test_reports_empty_metrics_without_enemy_detections() -> None:
    result = analyze_detections([_frame(0, (960, 540))])

    assert result["summary"]["crosshair"] == {
        "score_percent": None,
        "mean_head_error_px": None,
        "evaluated_frames": 0,
    }
    assert result["summary"]["aim_reaction"]["encounters"] == 0
    assert result["events"] == []


def test_rejects_out_of_order_frames() -> None:
    with pytest.raises(ValueError, match="sorted"):
        analyze_detections(
            [_frame(100, (0, 0)), _frame(50, (0, 0))]
        )


def test_vertical_offset_preserves_direction_and_avoids_cancellation():
    result = analyze_detections([
        _frame(0, (150, 156), enemies=[ENEMY]),
        _frame(100, (150, 116), enemies=[ENEMY]),
    ])["summary"]["vertical_placement"]
    assert result == {"mean_signed_offset_pct": 0.0, "mean_absolute_offset_pct": 10.0,
                      "evaluated_frames": 2, "below_frames": 1, "above_frames": 1, "level_frames": 0}


def test_ambiguous_legacy_targets_cannot_share_alignment_timer():
    other = dict(ENEMY, x=400)
    result = analyze_detections([_frame(0, (150, 136), enemies=[ENEMY, other])])
    assert result["summary"]["aim_reaction"]["measured_encounters"] == 0
    assert result["summary"]["vertical_placement"]["evaluated_frames"] == 0


def test_nonfinite_and_non_enemy_boxes_are_excluded():
    boxes = [dict(ENEMY, x=float('nan')), dict(ENEMY, h=float('inf')), dict(ENEMY, class_name='ally')]
    result = analyze_detections([_frame(0, (150, 136), enemies=boxes)])
    assert result["summary"]["crosshair"]["evaluated_frames"] == 0
