from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import cv2 as cv
import numpy as np

from scripts import prepare_yolo_dataset as builder


def _write_video(path: Path, frames: int = 10) -> None:
    writer = cv.VideoWriter(
        str(path), cv.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 24)
    )
    assert writer.isOpened()
    try:
        for value in range(frames):
            writer.write(np.full((24, 32, 3), value, dtype=np.uint8))
    finally:
        writer.release()


def _write_export(
    path: Path,
    *,
    subset: str = "Train",
    labeled_frames: dict[int, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labeled_frames = labeled_frames or {}
    with ZipFile(path, "w") as archive:
        archive.writestr("data.yaml", "names:\n  0: enemy\n")
        archive.writestr(
            f"{subset}.txt",
            "\n".join(
                f"data/images/{subset}/frame_{frame:06d}.png"
                for frame in range(10)
            )
            + "\n",
        )
        for frame, label in labeled_frames.items():
            archive.writestr(
                f"labels/{subset}/frame_{frame:06d}.txt", label + "\n"
            )


def test_read_export_clips_boxes_that_cross_an_image_edge(tmp_path: Path) -> None:
    archive_path = tmp_path / "round-001.zip"
    _write_export(
        archive_path,
        labeled_frames={2: "0 0.01 0.50 0.20 0.20"},
    )

    export = builder.read_export(archive_path, "train", "vod-99")

    assert export.clipped_boxes == 1
    assert export.labels[2] == "0 0.055000 0.500000 0.110000 0.200000\n"


def test_resolve_and_prepare_dataset_from_nested_exports(tmp_path: Path) -> None:
    exports_root = tmp_path / "exports"
    staging_root = tmp_path / "staging"
    source_video = staging_root / "vod-99" / "live" / "round-001-live.mp4"
    source_video.parent.mkdir(parents=True)
    _write_video(source_video)
    _write_export(
        exports_root / "train" / "vod-99" / "vod-99_round-001.zip",
        labeled_frames={2: "0 0.5 0.5 0.2 0.2", 3: "0 0.5 0.5 0.2 0.2", 4: "0 0.5 0.5 0.2 0.2"},
    )

    resolved, excluded = builder.resolve_plan(
        exports_root,
        staging_root,
        tmp_path / "legacy",
        0.05,
    )
    output = tmp_path / "dataset"
    summary = builder.prepare_clip(
        resolved[0],
        output,
        positive_fps=5.0,
        background_fps=2.0,
        jpeg_quality=90,
    )

    assert excluded == []
    assert resolved[0].video.path == source_video
    assert summary.selected_frames == 4
    assert summary.positive_images == 2
    assert summary.negative_images == 2
    assert len(list((output / "images" / "train").glob("*.jpg"))) == 4
    label_files = list((output / "labels" / "train").glob("*.txt"))
    assert len(label_files) == 4
    assert sum(bool(path.read_text(encoding="utf-8")) for path in label_files) == 2


def test_collect_exports_excludes_an_archive_with_wrong_internal_split(
    tmp_path: Path,
) -> None:
    _write_export(
        tmp_path / "exports" / "train" / "vod-99" / "vod-99_round-000.zip",
        subset="Train",
    )
    _write_export(
        tmp_path / "exports" / "train" / "vod-99" / "vod-99_round-001.zip",
        subset="Validation",
    )

    records, excluded = builder.collect_exports(tmp_path / "exports")

    assert len(records) == 1
    assert len(excluded) == 1
    assert "internal subset is val" in excluded[0]["reason"]
