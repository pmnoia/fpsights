from __future__ import annotations

from pathlib import Path

import cv2 as cv
import numpy as np

from src.pipeline.frame_reader import read_frames


def _write_test_video(path: Path) -> None:
    writer = cv.VideoWriter(
        str(path),
        cv.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for value in range(30):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()


def test_reads_only_requested_time_range(tmp_path: Path) -> None:
    video_path = tmp_path / "range.mp4"
    _write_test_video(video_path)

    frames = list(read_frames(video_path, start_ms=1_000, end_ms=2_000))

    assert len(frames) == 10
    assert frames[0][0] == 10
    assert frames[-1][0] == 19
