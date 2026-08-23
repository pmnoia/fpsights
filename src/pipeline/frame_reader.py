"""Video frame iteration utilities."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2 as cv


def read_frames(
    video_path: str | Path,
    frame_skip: int = 1,
    max_frames: int | None = None,
    start_ms: int = 0,
    end_ms: int | None = None,
) -> Iterator[tuple[int, Any]]:
    if frame_skip < 1:
        raise ValueError("frame_skip must be at least 1")

    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be at least 1")

    if start_ms < 0:
        raise ValueError("start_ms cannot be negative")

    if end_ms is not None and end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")

    video = cv.VideoCapture(str(video_path))

    if not video.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = float(video.get(cv.CAP_PROP_FPS))
    if fps <= 0:
        video.release()
        raise ValueError(f"Video reports an invalid frame rate: {video_path}")

    start_frame = int(start_ms / 1000 * fps)
    video.set(cv.CAP_PROP_POS_FRAMES, start_frame)
    frame_number = start_frame
    processed_count = 0

    try:
        while max_frames is None or processed_count < max_frames:
            timestamp_ms = int(round(frame_number / fps * 1000))
            if end_ms is not None and timestamp_ms >= end_ms:
                break

            success, frame = video.read()

            if not success:
                break

            if (frame_number - start_frame) % frame_skip == 0:
                yield frame_number, frame
                processed_count += 1

            frame_number += 1
    finally:
        video.release()
