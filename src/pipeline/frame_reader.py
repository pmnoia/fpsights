"""Video frame iteration utilities."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2 as cv


def read_frames(
    video_path: str | Path,
    frame_skip: int = 1,
    max_frames: int | None = None,
) -> Iterator[tuple[int, Any]]:
    if frame_skip < 1:
        raise ValueError("frame_skip must be at least 1")

    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be at least 1")

    video = cv.VideoCapture(str(video_path))

    if not video.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    frame_number = 0
    processed_count = 0

    try:
        while max_frames is None or processed_count < max_frames:
            success, frame = video.read()

            if not success:
                break

            if frame_number % frame_skip == 0:
                yield frame_number, frame
                processed_count += 1

            frame_number += 1
    finally:
        video.release()
