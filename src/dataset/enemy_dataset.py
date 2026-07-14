"""Build and populate an Ultralytics enemy-detection dataset."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2


DATASET_SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class FrameSample:
    """Metadata for one frame extracted from a source video."""

    source_video: str
    frame_file: str
    frame_index: int
    timestamp_ms: int


def create_dataset_layout(root: Path, *, overwrite_yaml: bool = False) -> Path:
    """Create the one-class Ultralytics dataset layout and return its YAML path."""

    root = root.expanduser().resolve()
    (root / "raw" / "images").mkdir(parents=True, exist_ok=True)

    for split in DATASET_SPLITS:
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)

    yaml_path = root / "data.yaml"
    if overwrite_yaml or not yaml_path.exists():
        yaml_path.write_text(
            "\n".join(
                (
                    f"path: {json.dumps(str(root))}",
                    "train: images/train",
                    "val: images/val",
                    "test: images/test",
                    "",
                    "names:",
                    "  0: enemy",
                    "",
                )
            ),
            encoding="utf-8",
        )

    return yaml_path


def sample_video_frames(
    video_path: Path,
    output_dir: Path,
    *,
    interval_seconds: float = 1.0,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    jpeg_quality: int = 95,
    overwrite: bool = False,
) -> list[FrameSample]:
    """Extract deterministic frame indices from a video at a fixed interval."""

    video_path = video_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()

    if not video_path.is_file():
        raise FileNotFoundError(f"Video does not exist: {video_path}")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    if start_seconds < 0:
        raise ValueError("start_seconds cannot be negative")
    if end_seconds is not None and end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 1 and 100")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"OpenCV could not open video: {video_path}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frame_count <= 0:
            raise ValueError(
                f"Video metadata is invalid: fps={fps}, frame_count={frame_count}"
            )

        interval_frames = max(1, round(interval_seconds * fps))
        start_frame = round(start_seconds * fps)
        end_frame = frame_count
        if end_seconds is not None:
            end_frame = min(frame_count, round(end_seconds * fps))

        if start_frame >= frame_count:
            raise ValueError("start_seconds is beyond the end of the video")

        output_dir.mkdir(parents=True, exist_ok=True)
        samples: list[FrameSample] = []

        for frame_index in range(start_frame, end_frame, interval_frames):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                raise RuntimeError(
                    f"Could not decode frame {frame_index} from {video_path}"
                )

            timestamp_ms = round(frame_index * 1000 / fps)
            frame_name = (
                f"{video_path.stem}_f{frame_index:08d}_t{timestamp_ms:010d}.jpg"
            )
            frame_path = output_dir / frame_name
            if frame_path.exists() and not overwrite:
                raise FileExistsError(
                    f"Frame already exists: {frame_path}. Use overwrite=True to replace it."
                )

            written = cv2.imwrite(
                str(frame_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
            )
            if not written:
                raise OSError(f"Could not write extracted frame: {frame_path}")

            samples.append(
                FrameSample(
                    source_video=str(video_path),
                    frame_file=str(frame_path),
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                )
            )

        return samples
    finally:
        capture.release()


def write_sampling_manifest(
    samples: list[FrameSample], manifest_path: Path, *, append: bool = True
) -> None:
    """Write frame metadata, replacing duplicate source/frame rows on reruns."""

    manifest_path = manifest_path.expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(FrameSample.__dataclass_fields__)
    indexed_samples: dict[tuple[str, int], FrameSample] = {}

    if append and manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
            for row in csv.DictReader(manifest_file):
                sample = FrameSample(
                    source_video=row["source_video"],
                    frame_file=row["frame_file"],
                    frame_index=int(row["frame_index"]),
                    timestamp_ms=int(row["timestamp_ms"]),
                )
                indexed_samples[(sample.source_video, sample.frame_index)] = sample

    for sample in samples:
        indexed_samples[(sample.source_video, sample.frame_index)] = sample

    ordered_samples = sorted(
        indexed_samples.values(), key=lambda sample: (sample.source_video, sample.frame_index)
    )

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(sample) for sample in ordered_samples)
