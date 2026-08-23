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
