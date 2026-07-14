from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.dataset.enemy_dataset import (
    create_dataset_layout,
    sample_video_frames,
    write_sampling_manifest,
)


def make_test_video(path: Path, *, fps: float = 5.0, frame_count: int = 10) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24)
    )
    assert writer.isOpened()
    try:
        for index in range(frame_count):
            frame = np.full((24, 32, 3), index * 10, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_create_dataset_layout(tmp_path: Path) -> None:
    root = tmp_path / "enemy_dataset"

    yaml_path = create_dataset_layout(root)

    assert yaml_path == root / "data.yaml"
    assert (root / "raw" / "images").is_dir()
    for split in ("train", "val", "test"):
        assert (root / "images" / split).is_dir()
        assert (root / "labels" / split).is_dir()

    yaml_text = yaml_path.read_text(encoding="utf-8")
    assert f'path: "{root}"' in yaml_text
    assert "  0: enemy" in yaml_text


def test_sample_video_frames_and_manifest(tmp_path: Path) -> None:
    video_path = tmp_path / "round.avi"
    output_dir = tmp_path / "raw" / "images"
    make_test_video(video_path)

    samples = sample_video_frames(
        video_path,
        output_dir,
        interval_seconds=0.4,
        start_seconds=0.2,
        end_seconds=1.4,
    )

    assert [sample.frame_index for sample in samples] == [1, 3, 5]
    assert [sample.timestamp_ms for sample in samples] == [200, 600, 1000]
    assert all(Path(sample.frame_file).is_file() for sample in samples)

    manifest_path = tmp_path / "sampling_manifest.csv"
    write_sampling_manifest(samples, manifest_path)
    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        rows = list(csv.DictReader(manifest_file))

    assert [int(row["frame_index"]) for row in rows] == [1, 3, 5]
    assert all(row["source_video"] == str(video_path) for row in rows)

    write_sampling_manifest(samples, manifest_path)
    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        rerun_rows = list(csv.DictReader(manifest_file))
    assert len(rerun_rows) == 3


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"interval_seconds": 0}, "interval_seconds"),
        ({"start_seconds": -1}, "start_seconds"),
        ({"start_seconds": 2, "end_seconds": 1}, "end_seconds"),
        ({"jpeg_quality": 101}, "jpeg_quality"),
    ],
)
def test_sample_video_frames_validates_options(
    tmp_path: Path, kwargs: dict[str, float | int], message: str
) -> None:
    video_path = tmp_path / "round.avi"
    make_test_video(video_path)

    with pytest.raises(ValueError, match=message):
        sample_video_frames(video_path, tmp_path / "frames", **kwargs)
