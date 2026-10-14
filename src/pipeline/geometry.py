"""Shared box geometry used by tracking, analytics, and lessons."""

from math import hypot
from typing import Any


def estimated_head(box: dict[str, Any]) -> tuple[float, float]:
    """Use the centre of the box at 18% of its height as a head estimate."""
    return box["x"] + box["w"] / 2, box["y"] + box["h"] * 0.18


def head_distance(x: float, y: float, box: dict[str, Any]) -> float:
    """Return the pixel distance from a point to the box's estimated head."""
    head_x, head_y = estimated_head(box)
    return hypot(x - head_x, y - head_y)


def box_overlap(left: dict[str, Any], right: dict[str, Any]) -> float:
    """Intersection over union: 0 means separate, 1 means identical."""
    x1 = max(left["x"], right["x"])
    y1 = max(left["y"], right["y"])
    x2 = min(left["x"] + left["w"], right["x"] + right["w"])
    y2 = min(left["y"] + left["h"], right["y"] + right["h"])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = left["w"] * left["h"] + right["w"] * right["h"] - intersection
    return intersection / union if union > 0 else 0.0
