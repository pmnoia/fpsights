"""Build a compact YOLO dataset from CVAT label-only video exports.

CVAT's Ultralytics exports contain one frame path per source-video frame and
label files only for frames that contain boxes. This utility recreates the
images from the original clips, keeps every positive frame, and samples empty
background frames at a configurable rate.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from zipfile import ZipFile

import cv2


FRAME_PATTERN = re.compile(r"frame_(\d+)", re.IGNORECASE)
CLIP_PATTERN = re.compile(r"vod-01-(\d+)$", re.IGNORECASE)
SPLITS = {"Train": "train", "Validation": "val", "Test": "test"}


@dataclass
class ClipSummary:
    split: str
    archive: str
    video: str
    fps: float
    source_frames: int
    selected_frames: int
    positive_frames: int
    negative_frames: int
    boxes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exports-root", type=Path, default=Path("cvat-annotated-files")
    )
    parser.add_argument("--videos-root", type=Path, default=Path("videos/vod-01_alive"))
    parser.add_argument("--output", type=Path, default=Path("datasets/vod-01-yolo"))
    parser.add_argument(
        "--background-fps",
        type=float,
        default=5.0,
        help="Sampling rate for frames without enemy boxes; positives are all kept.",
    )
    parser.add_argument("--jpeg-quality", type=int, default=92)
    return parser.parse_args()


def frame_number(path: str) -> int:
    match = FRAME_PATTERN.search(path)
    if not match:
        raise ValueError(f"Cannot read frame number from {path!r}")
    return int(match.group(1))


def read_export(
    archive_path: Path, source_split: str
) -> tuple[set[int], dict[int, str], int]:
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        list_name = next(
            (name for name in names if name.rsplit("/", 1)[-1] == f"{source_split}.txt"),
            None,
        )
        if list_name is None:
            raise ValueError(f"{archive_path} has no {source_split}.txt")

        yaml_name = next((name for name in names if name.endswith("data.yaml")), None)
        if yaml_name is None or "0: enemy" not in archive.read(yaml_name).decode("utf-8"):
            raise ValueError(f"{archive_path} does not define class 0 as enemy")

        listed_frames = {
            frame_number(line)
            for line in archive.read(list_name).decode("utf-8").splitlines()
            if line.strip()
        }
        labels: dict[int, str] = {}
        box_count = 0
        for name in names:
            if not name.startswith("labels/") or not name.endswith(".txt"):
                continue
            content = archive.read(name).decode("utf-8").strip()
            if not content:
                continue
            index = frame_number(name)
            rows = [row for row in content.splitlines() if row.strip()]
            for row in rows:
                fields = row.split()
                if len(fields) != 5 or fields[0] != "0":
                    raise ValueError(f"Invalid YOLO row in {archive_path}:{name}: {row}")
                values = [float(value) for value in fields[1:]]
                if not all(0.0 <= value <= 1.0 for value in values):
                    raise ValueError(f"Out-of-range box in {archive_path}:{name}: {row}")
                if values[2] <= 0.0 or values[3] <= 0.0:
                    raise ValueError(f"Empty box in {archive_path}:{name}: {row}")
            labels[index] = "\n".join(rows) + "\n"
            box_count += len(rows)
        return listed_frames, labels, box_count


def prepare_clip(
    archive_path: Path,
    source_split: str,
    output_split: str,
    videos_root: Path,
    output_root: Path,
    background_fps: float,
    jpeg_quality: int,
) -> ClipSummary:
    clip_match = CLIP_PATTERN.fullmatch(archive_path.stem)
    if not clip_match:
        raise ValueError(f"Unexpected archive name: {archive_path.name}")
    clip_number = int(clip_match.group(1))
    video_path = videos_root / f"vod-01-{clip_number}.mov"
    if not video_path.is_file():
        raise FileNotFoundError(video_path)

    listed_frames, labels, box_count = read_export(archive_path, source_split)
    video = cv2.VideoCapture(str(video_path))
    if not video.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")

    fps = float(video.get(cv2.CAP_PROP_FPS))
    source_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or source_frames <= 0:
        raise ValueError(f"Invalid video metadata for {video_path}")
    if len(listed_frames) != source_frames or listed_frames != set(range(source_frames)):
        raise ValueError(
            f"Frame mismatch for {archive_path.name}: export has {len(listed_frames)}, "
            f"video has {source_frames}"
        )

    background_stride = max(1, round(fps / background_fps))
    positives = set(labels)
    selected = positives | set(range(0, source_frames, background_stride))

    image_dir = output_root / "images" / output_split
    label_dir = output_root / "labels" / output_split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    frame_index = 0
    while frame_index < source_frames:
        ok, frame = video.read()
        if not ok:
            break
        if frame_index in selected:
            stem = f"vod-01-{clip_number:02d}_frame_{frame_index:06d}"
            image_path = image_dir / f"{stem}.jpg"
            label_path = label_dir / f"{stem}.txt"
            if not cv2.imwrite(
                str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
            ):
                raise RuntimeError(f"Failed to write {image_path}")
            label_path.write_text(labels.get(frame_index, ""), encoding="utf-8")
            written += 1
        frame_index += 1
    video.release()

    if frame_index != source_frames or written != len(selected):
        raise RuntimeError(
            f"Decoded {frame_index}/{source_frames} frames and wrote "
            f"{written}/{len(selected)} for {video_path}"
        )

    return ClipSummary(
        split=output_split,
        archive=str(archive_path),
        video=str(video_path),
        fps=fps,
        source_frames=source_frames,
        selected_frames=len(selected),
        positive_frames=len(positives),
        negative_frames=len(selected - positives),
        boxes=box_count,
    )


def main() -> None:
    args = parse_args()
    if args.background_fps <= 0:
        raise ValueError("--background-fps must be positive")
    if not 1 <= args.jpeg_quality <= 100:
        raise ValueError("--jpeg-quality must be between 1 and 100")
    if args.output.exists():
        raise FileExistsError(
            f"Output already exists: {args.output}. Choose a new path to avoid overwriting it."
        )

    summaries: list[ClipSummary] = []
    for source_split, output_split in SPLITS.items():
        split_dir = args.exports_root / source_split
        archives = sorted(split_dir.glob("*.zip"))
        if not archives:
            raise FileNotFoundError(f"No ZIP exports found in {split_dir}")
        for archive_path in archives:
            print(f"Preparing {archive_path.name} -> {output_split}", flush=True)
            summaries.append(
                prepare_clip(
                    archive_path,
                    source_split,
                    output_split,
                    args.videos_root,
                    args.output,
                    args.background_fps,
                    args.jpeg_quality,
                )
            )

    data_yaml = f"""path: {args.output.resolve()}
train: images/train
val: images/val
test: images/test
names:
  0: enemy
"""
    (args.output / "data.yaml").write_text(data_yaml, encoding="utf-8")
    totals: dict[str, dict[str, int]] = {}
    for split in ("train", "val", "test"):
        split_rows = [item for item in summaries if item.split == split]
        totals[split] = {
            "clips": len(split_rows),
            "images": sum(item.selected_frames for item in split_rows),
            "positive_images": sum(item.positive_frames for item in split_rows),
            "negative_images": sum(item.negative_frames for item in split_rows),
            "boxes": sum(item.boxes for item in split_rows),
        }
    summary = {
        "background_fps": args.background_fps,
        "jpeg_quality": args.jpeg_quality,
        "totals": totals,
        "clips": [asdict(item) for item in summaries],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
