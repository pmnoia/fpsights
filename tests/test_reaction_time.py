from __future__ import annotations

import pytest

from src.analysis.enemy_detector import Detection
from src.analysis.reaction_time import ReactionEvent, ReactionTimeCalculator


def enemy(box: tuple[int, int, int, int]) -> list[Detection]:
    return [Detection(box=box, confidence=0.9)]


def test_reports_start_of_sustained_aim_correction() -> None:
    calculator = ReactionTimeCalculator(
        confirmation_frames=2,
        minimum_distance_drop_px=8,
    )

    assert calculator.update(0, enemy((80, 40, 90, 60)), (100, 100)) is None
    assert calculator.update(100, enemy((76, 40, 86, 60)), (100, 100)) is None
    event = calculator.update(200, enemy((70, 40, 80, 60)), (100, 100))

    assert event == ReactionEvent(
        enemy_visible_timestamp_ms=0,
        response_timestamp_ms=100,
        reaction_time_ms=100,
    )


def test_reports_zero_when_crosshair_is_already_inside_enemy_box() -> None:
    calculator = ReactionTimeCalculator()

    event = calculator.update(500, enemy((40, 40, 60, 60)), (100, 100))

    assert event == ReactionEvent(500, 500, 0)


def test_closes_missed_encounter_after_allowed_gap() -> None:
    calculator = ReactionTimeCalculator(maximum_gap_frames=1)

    assert calculator.update(0, enemy((80, 40, 90, 60)), (100, 100)) is None
    assert calculator.update(100, [], (100, 100)) is None
    event = calculator.update(200, [], (100, 100))

    assert event == ReactionEvent(0, None, None)


def test_finish_returns_unresolved_encounter() -> None:
    calculator = ReactionTimeCalculator()
    calculator.update(250, enemy((80, 40, 90, 60)), (100, 100))

    assert calculator.finish() == ReactionEvent(250, None, None)
    assert calculator.finish() is None


def test_reaction_calculator_rejects_decreasing_timestamps() -> None:
    calculator = ReactionTimeCalculator()
    calculator.update(100, [], (100, 100))

    with pytest.raises(ValueError, match="ascending"):
        calculator.update(99, [], (100, 100))
