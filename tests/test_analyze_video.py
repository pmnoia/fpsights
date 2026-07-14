from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.analysis.analyze_video import analyze_video
from src.analysis.enemy_detector import Detection
from src.analysis.reaction_time import ReactionTimeCalculator


class SequenceDetector:
    def __init__(self, detections: list[list[Detection]]) -> None:
        self.detections = iter(detections)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        return next(self.detections)


class BatchSequenceDetector:
    def __init__(self, detections: list[list[Detection]]) -> None:
        self.detections = iter(detections)
        self.batch_lengths: list[int] = []

    def detect_batch(self, frames: list[np.ndarray]) -> list[list[Detection]]:
        self.batch_lengths.append(len(frames))
        return [next(self.detections) for _ in frames]


def make_test_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (100, 100)
    )
    assert writer.isOpened()
    try:
        for _ in range(4):
            writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    finally:
        writer.release()


def test_analyze_video_returns_reaction_events(tmp_path: Path) -> None:
    video_path = tmp_path / "round.avi"
    make_test_video(video_path)
    detector = SequenceDetector(
        [
            [Detection((80, 40, 90, 60), 0.9)],
            [Detection((76, 40, 86, 60), 0.9)],
            [Detection((70, 40, 80, 60), 0.9)],
            [],
        ]
    )
    calculator = ReactionTimeCalculator(
        confirmation_frames=2,
        minimum_distance_drop_px=8,
    )

    result = analyze_video(
        video_path,
        detector,
        reaction_calculator=calculator,
    )

    assert result["frames_processed"] == 4
    assert result["frame_width"] == 100
    assert result["frame_height"] == 100
    assert result["reaction_events"] == [
        {
            "enemy_visible_timestamp_ms": 0,
            "response_timestamp_ms": 100,
            "reaction_time_ms": 100,
        }
    ]


def test_analyze_video_batches_frames_without_changing_timestamps(tmp_path: Path) -> None:
    video_path = tmp_path / "round.avi"
    make_test_video(video_path)
    detector = BatchSequenceDetector(
        [
            [Detection((80, 40, 90, 60), 0.9)],
            [Detection((76, 40, 86, 60), 0.9)],
            [Detection((70, 40, 80, 60), 0.9)],
            [],
        ]
    )
    calculator = ReactionTimeCalculator(
        confirmation_frames=2,
        minimum_distance_drop_px=8,
    )

    result = analyze_video(
        video_path,
        detector,
        reaction_calculator=calculator,
        batch_size=3,
    )

    assert detector.batch_lengths == [3, 1]
    assert result["frames_processed"] == 4
    assert result["reaction_events"] == [
        {
            "enemy_visible_timestamp_ms": 0,
            "response_timestamp_ms": 100,
            "reaction_time_ms": 100,
        }
    ]
