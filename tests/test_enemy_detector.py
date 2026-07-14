from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.analysis.enemy_detector import Detection, EnemyDetector


class FakeModel:
    def __init__(self, boxes: object) -> None:
        self.boxes = boxes
        self.call: dict[str, object] | None = None

    def predict(self, **kwargs: object) -> list[SimpleNamespace]:
        self.call = kwargs
        return [SimpleNamespace(boxes=self.boxes)]


def test_detect_converts_clips_and_filters_yolo_results() -> None:
    boxes = SimpleNamespace(
        xyxy=np.array(
            [
                [-2.2, 3.1, 20.2, 21.8],
                [5.0, 5.0, 15.0, 15.0],
                [8.0, 8.0, 8.0, 12.0],
            ]
        ),
        conf=np.array([0.9, 0.8, 0.7]),
        cls=np.array([0, 1, 0]),
    )
    model = FakeModel(boxes)
    detector = EnemyDetector(model=model, confidence=0.5)
    frame = np.zeros((20, 30, 3), dtype=np.uint8)

    detections = detector.detect(frame)

    assert detections == [Detection(box=(0, 3, 21, 20), confidence=0.9)]
    assert model.call == {"source": frame, "conf": 0.5, "verbose": False}


def test_detect_returns_empty_list_when_model_has_no_boxes() -> None:
    detector = EnemyDetector(model=FakeModel(None))

    assert detector.detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_detect_batch_preserves_frame_order() -> None:
    first_boxes = SimpleNamespace(
        xyxy=np.array([[1.0, 2.0, 5.0, 8.0]]),
        conf=np.array([0.9]),
        cls=np.array([0]),
    )
    model = FakeModel(first_boxes)

    def predict(**kwargs: object) -> list[SimpleNamespace]:
        model.call = kwargs
        return [SimpleNamespace(boxes=first_boxes), SimpleNamespace(boxes=None)]

    model.predict = predict  # type: ignore[method-assign]
    detector = EnemyDetector(model=model, confidence=0.5)
    frames = [
        np.zeros((10, 10, 3), dtype=np.uint8),
        np.zeros((20, 20, 3), dtype=np.uint8),
    ]

    detections = detector.detect_batch(frames)

    assert detections == [[Detection(box=(1, 2, 5, 8), confidence=0.9)], []]
    assert model.call == {
        "source": frames,
        "conf": 0.5,
        "verbose": False,
        "batch": 2,
    }


def test_detector_validates_inputs() -> None:
    with pytest.raises(ValueError, match="model_path"):
        EnemyDetector()
    with pytest.raises(ValueError, match="confidence"):
        EnemyDetector(model=FakeModel(None), confidence=1.1)

    detector = EnemyDetector(model=FakeModel(None))
    with pytest.raises(ValueError, match="BGR"):
        detector.detect(np.zeros((10, 10), dtype=np.uint8))
