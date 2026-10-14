from __future__ import annotations

import cv2 as cv
import numpy as np

from src.pipeline.positioning import MinimapTracker


def test_tracks_white_minimap_marker_and_writes_heatmap(tmp_path) -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv.rectangle(frame, (180, 250), (190, 258), (255, 255, 255), -1)

    tracker = MinimapTracker()
    point = tracker.observe(frame, "segment-1")

    assert point is not None
    assert 0 < point["x"] < 1
    assert 0 < point["y"] < 1

    output = tmp_path / "heatmap.png"
    assert tracker.render([point], output)
    assert output.stat().st_size > 0


def test_heatmap_accumulates_repeated_visits(tmp_path, monkeypatch) -> None:
    tracker = MinimapTracker()
    tracker.background = np.zeros((200, 200, 3), dtype=np.uint8)
    captured = []
    original = cv.applyColorMap

    def capture(density, palette):
        captured.append(density.copy())
        return original(density, palette)

    monkeypatch.setattr(cv, "applyColorMap", capture)
    points = [{"x": 0.25, "y": 0.5}] * 10 + [{"x": 0.75, "y": 0.5}]
    assert tracker.render(points, tmp_path / "heatmap.png")
    assert captured[0][100, 50] > captured[0][100, 150] * 5


def marker_frame(x=180, color=(255, 255, 255)):
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv.rectangle(frame, (x, 250), (x + 10, 258), color, -1)
    return frame


def test_yellow_icons_are_not_pov_markers():
    assert MinimapTracker().observe(marker_frame(color=(0, 220, 255)), "s1") is None


def test_ambiguous_white_markers_are_not_guessed():
    frame = marker_frame()
    cv.rectangle(frame, (280, 250), (290, 258), (255, 255, 255), -1)
    assert MinimapTracker().observe(frame, "s1") is None


def test_pov_jump_reacquires_without_staying_locked():
    tracker = MinimapTracker()
    assert tracker.observe(marker_frame(), "s1")
    for _ in range(3):
        assert tracker.observe(marker_frame(280), "s1") is None
    assert tracker.observe(marker_frame(280), "s1")


def test_marker_size_and_movement_scale_with_resolution():
    tracker = MinimapTracker()
    for x in (180, 210):
        frame = cv.resize(marker_frame(x), (1280, 720), interpolation=cv.INTER_NEAREST)
        assert tracker.observe(frame, "s1")


def test_new_segment_resets_position():
    tracker = MinimapTracker()
    assert tracker.observe(marker_frame(), "s1")
    assert tracker.observe(marker_frame(280), "s2")
