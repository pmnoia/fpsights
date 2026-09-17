"""Approximate player movement from the Valorant minimap marker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np


class MinimapTracker:
    """Track the small yellow player marker in the top-left minimap."""

    def __init__(self) -> None:
        self.previous: tuple[float, float] | None = None
        self.segment_id: str | None = None
        self.background: np.ndarray | None = None

    def observe(self, frame: np.ndarray, segment_id: str) -> dict[str, float] | None:
        if segment_id != self.segment_id:
            self.segment_id = segment_id
            self.previous = None

        roi = _minimap_roi(frame)
        if self.background is None:
            self.background = roi.copy()

        candidates = _yellow_candidates(roi)
        if not candidates:
            return None

        if self.previous is None:
            selected = max(candidates, key=lambda item: item[0])
        else:
            selected = min(
                candidates,
                key=lambda item: (
                    (item[1] - self.previous[0]) ** 2
                    + (item[2] - self.previous[1]) ** 2
                ),
            )
            distance = (
                (selected[1] - self.previous[0]) ** 2
                + (selected[2] - self.previous[1]) ** 2
            ) ** 0.5
            if distance > 45:
                return None

        _, x, y = selected
        self.previous = (x, y)
        height, width = roi.shape[:2]
        return {"x": round(x / width, 6), "y": round(y / height, 6)}

    def render(self, points: list[dict[str, Any]], output_path: Path) -> bool:
        if self.background is None or not points:
            return False

        background = self.background.copy()
        height, width = background.shape[:2]
        density = np.zeros((height, width), dtype=np.float32)
        radius = max(10, round(min(width, height) * 0.035))

        for point in points:
            x = min(width - 1, max(0, round(float(point["x"]) * width)))
            y = min(height - 1, max(0, round(float(point["y"]) * height)))
            cv.circle(density, (x, y), radius, 1.0, -1, cv.LINE_AA)

        density = cv.GaussianBlur(density, (0, 0), sigmaX=radius * 1.4)
        maximum = float(density.max())
        if maximum <= 0:
            return False

        normalized = np.uint8(np.clip(density / maximum * 255, 0, 255))
        colorized = cv.applyColorMap(normalized, cv.COLORMAP_TURBO)
        alpha = (normalized.astype(np.float32) / 255.0 * 0.78)[..., None]
        blended = (
            background.astype(np.float32) * (1.0 - alpha)
            + colorized.astype(np.float32) * alpha
        ).astype(np.uint8)

        cv.rectangle(blended, (0, 0), (width, 34), (7, 13, 20), -1)
        cv.putText(
            blended,
            f"PLAYER MOVEMENT HEATMAP - {len(points)} samples",
            (12, 23),
            cv.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv.LINE_AA,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return bool(cv.imwrite(str(output_path), blended))


def _minimap_roi(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    return frame[: max(1, round(height * 0.37)), : max(1, round(width * 0.225))]


def _yellow_candidates(roi: np.ndarray) -> list[tuple[int, float, float]]:
    hsv = cv.cvtColor(roi, cv.COLOR_BGR2HSV)
    mask = cv.inRange(hsv, (20, 100, 120), (45, 255, 255))
    _, _, stats, centroids = cv.connectedComponentsWithStats(mask)
    height, width = roi.shape[:2]
    candidates: list[tuple[int, float, float]] = []

    for stat, centroid in zip(stats[1:], centroids[1:]):
        x, y, component_width, component_height, area = map(int, stat)
        if not 8 <= area <= 120:
            continue
        if component_width > 22 or component_height > 16:
            continue
        if x >= width * 0.85 or y <= height * 0.1:
            continue
        candidates.append((area, float(centroid[0]), float(centroid[1])))

    return candidates
