"""Small application-facing wrapper around an Ultralytics YOLO model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Detection:
    """One visible enemy in frame pixel coordinates."""

    box: tuple[int, int, int, int]
    confidence: float


class EnemyDetector:
    """Detect enemies while keeping Ultralytics out of the rest of FPSights."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        confidence: float = 0.25,
        model: Any | None = None,
    ) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if model is None and model_path is None:
            raise ValueError("model_path is required when model is not provided")

        self.confidence = confidence
        self._model = model if model is not None else self._load_model(model_path)

    @staticmethod
    def _load_model(model_path: str | Path | None) -> Any:
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError(
                "Ultralytics is not installed. Run: pip install -r requirements.txt"
            ) from error

        return YOLO(str(model_path))

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Return valid class-0 enemy boxes for one BGR video frame."""

        self._validate_frame(frame)

        height, width = frame.shape[:2]
        results = self._model.predict(
            source=frame,
            conf=self.confidence,
            verbose=False,
        )
        if not results:
            return []

        return self._parse_result(results[0], width, height)

    def detect_batch(self, frames: Sequence[np.ndarray]) -> list[list[Detection]]:
        """Detect enemies in a frame batch while preserving input order."""

        if not frames:
            return []
        for frame in frames:
            self._validate_frame(frame)

        results = self._model.predict(
            source=list(frames),
            conf=self.confidence,
            verbose=False,
            batch=len(frames),
        )
        if len(results) != len(frames):
            raise RuntimeError(
                f"YOLO returned {len(results)} results for {len(frames)} frames"
            )

        return [
            self._parse_result(result, frame.shape[1], frame.shape[0])
            for frame, result in zip(frames, results, strict=True)
        ]

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be a BGR image with shape (height, width, 3)")

    def _parse_result(
        self,
        result: Any,
        width: int,
        height: int,
    ) -> list[Detection]:
        if result.boxes is None:
            return []

        boxes = _as_list(result.boxes.xyxy)
        confidences = _as_list(result.boxes.conf)
        classes = _as_list(result.boxes.cls)

        detections: list[Detection] = []
        for raw_box, raw_confidence, raw_class in zip(
            boxes, confidences, classes, strict=True
        ):
            confidence = float(raw_confidence)
            if int(raw_class) != 0 or confidence < self.confidence:
                continue

            x_min = max(0, min(width, math.floor(float(raw_box[0]))))
            y_min = max(0, min(height, math.floor(float(raw_box[1]))))
            x_max = max(0, min(width, math.ceil(float(raw_box[2]))))
            y_max = max(0, min(height, math.ceil(float(raw_box[3]))))
            if x_max <= x_min or y_max <= y_min:
                continue

            detections.append(
                Detection(
                    box=(x_min, y_min, x_max, y_max),
                    confidence=confidence,
                )
            )

        return detections


def _as_list(value: Any) -> list[Any]:
    """Convert a tensor-like Ultralytics value into a normal Python list."""

    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)
