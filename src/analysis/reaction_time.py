"""Estimate reaction time from enemy boxes and a fixed center crosshair."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.analysis.enemy_detector import Detection


@dataclass(frozen=True)
class ReactionEvent:
    """One enemy encounter and its measured response, if available."""

    enemy_visible_timestamp_ms: int
    response_timestamp_ms: int | None
    reaction_time_ms: int | None


class ReactionTimeCalculator:
    """Find the first sustained aim correction during each enemy encounter."""

    def __init__(
        self,
        *,
        confirmation_frames: int = 2,
        minimum_distance_drop_px: float = 8.0,
        maximum_gap_frames: int = 2,
    ) -> None:
        if confirmation_frames < 1:
            raise ValueError("confirmation_frames must be at least 1")
        if minimum_distance_drop_px <= 0:
            raise ValueError("minimum_distance_drop_px must be greater than zero")
        if maximum_gap_frames < 0:
            raise ValueError("maximum_gap_frames cannot be negative")

        self.confirmation_frames = confirmation_frames
        self.minimum_distance_drop_px = minimum_distance_drop_px
        self.maximum_gap_frames = maximum_gap_frames

        self._first_visible_timestamp_ms: int | None = None
        self._distance_history: list[tuple[int, float]] = []
        self._missing_frames = 0
        self._response_reported = False
        self._last_timestamp_ms: int | None = None

    def update(
        self,
        timestamp_ms: int,
        detections: list[Detection],
        frame_size: tuple[int, int],
    ) -> ReactionEvent | None:
        """Process one frame and return an event when its result becomes known."""

        if timestamp_ms < 0:
            raise ValueError("timestamp_ms cannot be negative")
        if self._last_timestamp_ms is not None and timestamp_ms < self._last_timestamp_ms:
            raise ValueError("timestamps must be processed in ascending order")
        self._last_timestamp_ms = timestamp_ms

        width, height = frame_size
        if width <= 0 or height <= 0:
            raise ValueError("frame_size values must be greater than zero")

        if not detections:
            return self._handle_missing_frame()

        self._missing_frames = 0
        crosshair = (width / 2.0, height / 2.0)
        distance = min(
            _distance_from_point_to_box(crosshair, detection.box)
            for detection in detections
        )

        if self._first_visible_timestamp_ms is None:
            self._first_visible_timestamp_ms = timestamp_ms
            self._distance_history = [(timestamp_ms, distance)]
            if distance == 0:
                self._response_reported = True
                return ReactionEvent(timestamp_ms, timestamp_ms, 0)
            return None

        if self._response_reported:
            return None

        self._distance_history.append((timestamp_ms, distance))
        window_size = self.confirmation_frames + 1
        if len(self._distance_history) < window_size:
            return None

        window = self._distance_history[-window_size:]
        distances = [item[1] for item in window]
        is_sustained_correction = all(
            current < previous
            for previous, current in zip(distances, distances[1:])
        )
        total_drop = distances[0] - distances[-1]
        if not is_sustained_correction or total_drop < self.minimum_distance_drop_px:
            return None

        response_timestamp_ms = window[1][0]
        reaction_time_ms = response_timestamp_ms - self._first_visible_timestamp_ms
        self._response_reported = True
        return ReactionEvent(
            enemy_visible_timestamp_ms=self._first_visible_timestamp_ms,
            response_timestamp_ms=response_timestamp_ms,
            reaction_time_ms=reaction_time_ms,
        )

    def finish(self) -> ReactionEvent | None:
        """Close an unfinished encounter at the end of a video."""

        if self._first_visible_timestamp_ms is None or self._response_reported:
            self._reset_encounter()
            return None

        event = ReactionEvent(self._first_visible_timestamp_ms, None, None)
        self._reset_encounter()
        return event

    def _handle_missing_frame(self) -> ReactionEvent | None:
        if self._first_visible_timestamp_ms is None:
            return None

        self._missing_frames += 1
        self._distance_history.clear()
        if self._missing_frames <= self.maximum_gap_frames:
            return None

        event = None
        if not self._response_reported:
            event = ReactionEvent(self._first_visible_timestamp_ms, None, None)
        self._reset_encounter()
        return event

    def _reset_encounter(self) -> None:
        self._first_visible_timestamp_ms = None
        self._distance_history.clear()
        self._missing_frames = 0
        self._response_reported = False


def _distance_from_point_to_box(
    point: tuple[float, float], box: tuple[int, int, int, int]
) -> float:
    """Return zero inside the box, otherwise Euclidean distance to its edge."""

    x, y = point
    x_min, y_min, x_max, y_max = box
    dx = max(x_min - x, 0.0, x - x_max)
    dy = max(y_min - y, 0.0, y - y_max)
    return math.hypot(dx, dy)
