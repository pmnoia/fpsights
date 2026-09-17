from __future__ import annotations

import cv2 as cv
import numpy as np

from src.pipeline.positioning import MinimapTracker


def test_tracks_yellow_minimap_marker_and_writes_heatmap(tmp_path) -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv.rectangle(frame, (180, 250), (190, 258), (0, 220, 255), -1)

    tracker = MinimapTracker()
    point = tracker.observe(frame, "segment-1")

    assert point is not None
    assert 0 < point["x"] < 1
    assert 0 < point["y"] < 1

    output = tmp_path / "heatmap.png"
    assert tracker.render([point], output)
    assert output.stat().st_size > 0
