"""Build a leakage-safe YOLO dataset from label-only CVAT video exports.

CVAT's Ultralytics YOLO exports for video tasks contain a frame list and
labels, but not the source images. This command recreates only reviewed frames
from original live-round clips. It is intentionally conservative:

* folder splits (``train``/``val``/``test``) are authoritative;
* no unreviewed video frame becomes a negative example;
* source VODs cannot appear in more than one split;
* CVAT tasks are matched to clips by ordered frame-count alignment; and
* a resolved manifest records every mapping for reproducibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import cv2


FRAME_PATTERN = re.compile(r"frame_(\d+)", re.IGNORECASE)
ROUND_PATTERN = re.compile(r"round[-_](\d+)", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(\d+)")
DIRECTORY_SPLITS = {"train": "train", "val": "val", "test": "test"}
CVAT_LIST_SPLITS = {
    "Train.txt": "train",
    "Validation.txt": "val",
    "Test.txt": "test",
}


@dataclass(frozen=True)
class ExportInfo:
    archive_path: Path
    output_split: str
    source_id: str
    source_subset: str
    listed_frames: tuple[int, ...]
    labels: dict[int, str]
    box_count: int
    clipped_boxes: int
    sha256: str

    @property
    def maximum_frame(self) -> int:
        return self.listed_frames[-1]


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    frame_count: int
    fps: float


@dataclass(frozen=True)
class ResolvedClip:
    export: ExportInfo
    video: VideoInfo
    frame_count_delta: int
    frame_count_drift: float


@dataclass
class ClipSummary:
    split: str
    source_id: str
    archive: str
    video: str
    fps: float
    source_frames: int
    reviewed_frames: int
    selected_frames: int
    positive_images: int
    negative_images: int
    boxes: int
    clipped_boxes: int
    frame_count_delta: int
    frame_count_drift: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exports-root",
        type=Path,
        default=Path("cvat-exports"),
        help="CVAT exports arranged as <split>/<source-vod>/*.zip.",
    )
    parser.add_argument(
        "--staging-root",
        type=Path,
        default=Path("staging/cvat"),
        help="Root containing <source-vod>/live/*.mp4 clips.",
    )
    parser.add_argument(
        "--legacy-vod01-root",
        type=Path,
        default=Path("videos/vod-01_alive"),
        help="Legacy source clips for the original VOD-01 CVAT exports.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/fpsights-v2"),
        help="New dataset directory. It must not already exist.",
    )
    parser.add_argument(
        "--positive-fps",
        type=float,
        default=5.0,
        help="Maximum retained positive-frame rate per clip (default: 5).",
    )
    parser.add_argument(
        "--background-fps",
        type=float,
        default=2.0,
        help="Maximum retained reviewed negative-frame rate per clip (default: 2).",
    )
    parser.add_argument("--jpeg-quality", type=int, default=92)
    parser.add_argument(
        "--max-frame-drift",
        type=float,
        default=0.05,
        help="Largest allowed relative frame-count mismatch when matching a ZIP to a clip.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate exports and print the resolved plan without writing images.",
    )
    return parser.parse_args()


def _natural_key(value: str) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in NUMBER_PATTERN.split(value)
    ]


def _frame_number(value: str) -> int:
    match = FRAME_PATTERN.search(value)
    if not match:
        raise ValueError(f"Cannot read a frame number from {value!r}")
    return int(match.group(1))


def _round_number(value: str) -> int:
    match = ROUND_PATTERN.search(value)
    if not match:
        raise ValueError(f"Cannot read a round number from {value!r}")
    return int(match.group(1))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_yolo_row(
    row: str, archive_path: Path, member_name: str
) -> tuple[str, bool]:
    fields = row.split()
    if len(fields) != 5 or fields[0] != "0":
        raise ValueError(
            f"Invalid YOLO row in {archive_path}:{member_name}: {row}"
        )
    try:
        center_x, center_y, width, height = (
            float(value) for value in fields[1:]
        )
    except ValueError as error:
        raise ValueError(
            f"Invalid numeric YOLO row in {archive_path}:{member_name}: {row}"
        ) from error
    values = (center_x, center_y, width, height)
    if (
        not all(0.0 <= value <= 1.0 for value in values)
        or width <= 0
        or height <= 0
    ):
        raise ValueError(
            f"Out-of-range or empty YOLO box in {archive_path}:{member_name}: {row}"
        )

    original = (
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    )
    left, top, right, bottom = (
        max(0.0, original[0]),
        max(0.0, original[1]),
        min(1.0, original[2]),
        min(1.0, original[3]),
    )
    clipped = (left, top, right, bottom) != original
    if right <= left or bottom <= top:
        raise ValueError(
            f"Empty YOLO box after clipping in {archive_path}:{member_name}: {row}"
        )
    normalised = (
        f"0 {(left + right) / 2:.6f} {(top + bottom) / 2:.6f} "
        f"{right - left:.6f} {bottom - top:.6f}"
    )
    return normalised, clipped


def read_export(
    archive_path: Path, output_split: str, source_id: str
) -> ExportInfo:
    """Read one label-only CVAT export and validate its annotations."""
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        list_name = next(
            (name for name in names if Path(name).name in CVAT_LIST_SPLITS), None
        )
        if list_name is None:
            raise ValueError(f"{archive_path} has no CVAT frame list")
        source_subset = CVAT_LIST_SPLITS[Path(list_name).name]
        yaml_name = next((name for name in names if name.endswith("data.yaml")), None)
        if yaml_name is None:
            raise ValueError(f"{archive_path} has no data.yaml")
        yaml_text = archive.read(yaml_name).decode("utf-8")
        if not re.search(r"(?m)^\s*0\s*:\s*enemy\s*$", yaml_text):
            raise ValueError(f"{archive_path} does not define class 0 as enemy")

        listed_frames = tuple(
            sorted(
                {
                    _frame_number(line)
                    for line in archive.read(list_name).decode("utf-8").splitlines()
                    if line.strip()
                }
            )
        )
        if not listed_frames:
            raise ValueError(f"{archive_path} has an empty CVAT frame list")

        labels: dict[int, str] = {}
        box_count = 0
        clipped_boxes = 0
        for name in names:
            if not name.startswith("labels/") or not name.endswith(".txt"):
                continue
            frame = _frame_number(name)
            if frame not in listed_frames:
                raise ValueError(
                    f"{archive_path}:{name} labels a frame outside its frame list"
                )
            rows = [
                row
                for row in archive.read(name).decode("utf-8").splitlines()
                if row.strip()
            ]
            if not rows:
                continue
            normalised_rows: list[str] = []
            for row in rows:
                normalised, clipped = _normalise_yolo_row(row, archive_path, name)
                normalised_rows.append(normalised)
                clipped_boxes += int(clipped)
            labels[frame] = "\n".join(normalised_rows) + "\n"
            box_count += len(normalised_rows)

    return ExportInfo(
        archive_path=archive_path,
        output_split=output_split,
        source_id=source_id,
        source_subset=source_subset,
        listed_frames=listed_frames,
        labels=labels,
        box_count=box_count,
        clipped_boxes=clipped_boxes,
        sha256=_sha256(archive_path),
    )


def collect_exports(
    exports_root: Path,
) -> tuple[list[ExportInfo], list[dict[str, str]]]:
    """Discover exports and ignore files stored under an incompatible split."""
    if not exports_root.is_dir():
        raise FileNotFoundError(
            f"Could not find CVAT exports directory: {exports_root}"
        )

    records: list[ExportInfo] = []
    excluded: list[dict[str, str]] = []
    seen_sources: dict[str, str] = {}
    for split_directory in sorted(
        exports_root.iterdir(), key=lambda item: _natural_key(item.name)
    ):
        if (
            not split_directory.is_dir()
            or split_directory.name not in DIRECTORY_SPLITS
        ):
            continue
        output_split = DIRECTORY_SPLITS[split_directory.name]
        for source_directory in sorted(
            split_directory.iterdir(), key=lambda item: _natural_key(item.name)
        ):
            if not source_directory.is_dir():
                continue
            source_id = source_directory.name
            previous_split = seen_sources.setdefault(source_id, output_split)
            if previous_split != output_split:
                raise ValueError(
                    f"Source VOD {source_id} appears in both {previous_split} and "
                    f"{output_split}"
                )
            archives = sorted(
                source_directory.glob("*.zip"),
                key=lambda item: _natural_key(item.name),
            )
            if not archives:
                raise FileNotFoundError(f"No ZIP exports found in {source_directory}")
            for archive_path in archives:
                record = read_export(archive_path, output_split, source_id)
                if record.source_subset != output_split:
                    excluded.append(
                        {
                            "archive": str(archive_path),
                            "reason": (
                                f"CVAT internal subset is {record.source_subset}, but "
                                f"the directory split is {output_split}"
                            ),
                        }
                    )
                    continue
                # A handful of auto-segmented clips contain only a few frames
                # and no boxes. They add no useful negative diversity and are
                # too short for reliable frame-count matching after CVAT's
                # video conversion.
                if not record.labels and len(record.listed_frames) < 10:
                    excluded.append(
                        {
                            "archive": str(archive_path),
                            "reason": (
                                "contains fewer than 10 reviewed frames and no "
                                "enemy labels"
                            ),
                        }
                    )
                    continue
                records.append(record)

    if not records:
        raise FileNotFoundError(f"No usable ZIP exports found in {exports_root}")

    by_hash: dict[str, list[ExportInfo]] = {}
    for record in records:
        by_hash.setdefault(record.sha256, []).append(record)
    duplicates = [
        items
        for items in by_hash.values()
        if len({item.output_split for item in items}) > 1
    ]
    if duplicates:
        details = "; ".join(
            ", ".join(str(item.archive_path) for item in items)
            for items in duplicates
        )
        raise ValueError(
            f"Identical CVAT exports appear across data splits: {details}"
        )
    return records, excluded


def _probe_video(path: Path) -> VideoInfo:
    video = cv2.VideoCapture(str(path))
    if not video.isOpened():
        raise RuntimeError(f"Could not open source video: {path}")
    try:
        fps = float(video.get(cv2.CAP_PROP_FPS))
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        video.release()
    if fps <= 0 or frame_count <= 0:
        raise ValueError(f"Invalid video metadata for {path}")
    return VideoInfo(path=path, frame_count=frame_count, fps=fps)


def _candidate_videos(
    source_id: str, staging_root: Path, legacy_vod01_root: Path
) -> list[VideoInfo]:
    candidates: list[Path] = []
    live_directory = staging_root / source_id / "live"
    if live_directory.is_dir():
        candidates.extend(
            sorted(live_directory.glob("*.*"), key=lambda item: _natural_key(item.name))
        )
    if source_id == "vod-01" and legacy_vod01_root.is_dir():
        candidates.extend(
            sorted(
                legacy_vod01_root.glob("vod-01-*.mov"),
                key=lambda item: _natural_key(item.name),
            )
        )

    seen: set[Path] = set()
    videos: list[VideoInfo] = []
    for candidate in candidates:
        if candidate.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        videos.append(_probe_video(candidate))
    if not videos:
        raise FileNotFoundError(
            f"No live clips found for {source_id}. Looked in {live_directory} "
            f"and {legacy_vod01_root}."
        )
    return videos


def _align_exports_to_videos(
    exports: list[ExportInfo],
    videos: list[VideoInfo],
    max_frame_drift: float,
) -> list[ResolvedClip]:
    """Match ordered CVAT tasks to ordered clips while allowing missing clips."""
    exports = sorted(exports, key=lambda item: _natural_key(item.archive_path.name))
    videos = sorted(videos, key=lambda item: _natural_key(item.path.name))
    if len(videos) < len(exports):
        raise ValueError(
            f"Only {len(videos)} source clips are available for {len(exports)} CVAT exports"
        )

    skip_cost = 0.03

    @lru_cache(maxsize=None)
    def solve(
        export_index: int, video_index: int
    ) -> tuple[float, tuple[int, ...]]:
        if export_index == len(exports):
            return (skip_cost * (len(videos) - video_index), ())
        if len(videos) - video_index < len(exports) - export_index:
            return (float("inf"), ())

        best_cost = float("inf")
        best_mapping: tuple[int, ...] = ()
        current_export = exports[export_index]
        current_video = videos[video_index]
        expected_frames = current_export.maximum_frame + 1
        drift = abs(current_video.frame_count - expected_frames) / current_video.frame_count
        if drift <= max_frame_drift:
            remainder_cost, remainder_mapping = solve(
                export_index + 1, video_index + 1
            )
            candidate_cost = drift + remainder_cost
            if candidate_cost < best_cost:
                best_cost = candidate_cost
                best_mapping = (video_index,) + remainder_mapping

        skip_remainder_cost, skip_remainder_mapping = solve(
            export_index, video_index + 1
        )
        candidate_cost = skip_cost + skip_remainder_cost
        if candidate_cost < best_cost:
            best_cost = candidate_cost
            best_mapping = skip_remainder_mapping
        return best_cost, best_mapping

    cost, mapping = solve(0, 0)
    if cost == float("inf") or len(mapping) != len(exports):
        raise ValueError(
            "Could not safely map CVAT exports to source clips. Check task names "
            "and source clip files."
        )

    resolved: list[ResolvedClip] = []
    for export, video_index in zip(exports, mapping):
        video = videos[video_index]
        delta = video.frame_count - (export.maximum_frame + 1)
        drift = abs(delta) / video.frame_count
        if drift > max_frame_drift:
            raise ValueError(
                f"Unsafe mapping for {export.archive_path}: {video.path} differs "
                f"by {drift:.1%}"
            )
        resolved.append(
            ResolvedClip(
                export=export,
                video=video,
                frame_count_delta=delta,
                frame_count_drift=drift,
            )
        )
    return resolved


def resolve_plan(
    exports_root: Path,
    staging_root: Path,
    legacy_vod01_root: Path,
    max_frame_drift: float,
) -> tuple[list[ResolvedClip], list[dict[str, str]]]:
    exports, excluded = collect_exports(exports_root)
    by_source: dict[str, list[ExportInfo]] = {}
    for export in exports:
        by_source.setdefault(export.source_id, []).append(export)

    resolved: list[ResolvedClip] = []
    for source_id, source_exports in sorted(
        by_source.items(), key=lambda item: _natural_key(item[0])
    ):
        videos = _candidate_videos(source_id, staging_root, legacy_vod01_root)
        resolved.extend(
            _align_exports_to_videos(source_exports, videos, max_frame_drift)
        )
    return (
        sorted(
            resolved,
            key=lambda item: (
                item.export.output_split,
                _natural_key(item.export.source_id),
                _natural_key(item.export.archive_path.name),
            ),
        ),
        excluded,
    )


def _sample_frame_numbers(
    frames: Iterable[int], fps: float, target_fps: float
) -> set[int]:
    """Keep the first reviewed frame in each temporal sampling interval."""
    stride = max(1, round(fps / target_fps))
    selected: set[int] = set()
    last_selected: int | None = None
    for frame in sorted(frames):
        if last_selected is None or frame - last_selected >= stride:
            selected.add(frame)
            last_selected = frame
    return selected


def _selected_frames(
    export: ExportInfo,
    fps: float,
    positive_fps: float,
    background_fps: float,
) -> set[int]:
    positives = _sample_frame_numbers(export.labels, fps, positive_fps)
    negatives = _sample_frame_numbers(
        (frame for frame in export.listed_frames if frame not in export.labels),
        fps,
        background_fps,
    )
    return positives | negatives


def _output_stem(resolved: ResolvedClip, frame_number: int) -> str:
    archive_round = _round_number(resolved.export.archive_path.stem)
    return (
        f"{resolved.export.source_id}_task_{archive_round:03d}_"
        f"frame_{frame_number:06d}"
    )


def prepare_clip(
    resolved: ResolvedClip,
    output_root: Path,
    positive_fps: float,
    background_fps: float,
    jpeg_quality: int,
) -> ClipSummary:
    export = resolved.export
    selected = _selected_frames(
        export, resolved.video.fps, positive_fps, background_fps
    )
    if not selected:
        raise ValueError(f"No frames selected from {export.archive_path}")
    if max(selected) >= resolved.video.frame_count:
        raise ValueError(
            f"{export.archive_path} references a frame beyond {resolved.video.path}"
        )

    image_directory = output_root / "images" / export.output_split
    label_directory = output_root / "labels" / export.output_split
    image_directory.mkdir(parents=True, exist_ok=True)
    label_directory.mkdir(parents=True, exist_ok=True)

    video = cv2.VideoCapture(str(resolved.video.path))
    if not video.isOpened():
        raise RuntimeError(f"Could not open source video: {resolved.video.path}")
    written: set[int] = set()
    try:
        requested = iter(sorted(selected))
        next_requested = next(requested, None)
        frame_number = 0
        while next_requested is not None:
            ok, frame = video.read()
            if not ok:
                break
            if frame_number == next_requested:
                stem = _output_stem(resolved, frame_number)
                image_path = image_directory / f"{stem}.jpg"
                label_path = label_directory / f"{stem}.txt"
                if not cv2.imwrite(
                    str(image_path),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
                ):
                    raise RuntimeError(f"Could not write {image_path}")
                label_path.write_text(
                    export.labels.get(frame_number, ""), encoding="utf-8"
                )
                written.add(frame_number)
                next_requested = next(requested, None)
            frame_number += 1
    finally:
        video.release()
    if written != selected:
        missing = sorted(selected - written)
        raise RuntimeError(
            f"Could not decode {len(missing)} selected frame(s) from "
            f"{resolved.video.path}; first missing frame: {missing[0]}"
        )

    positives = selected & set(export.labels)
    return ClipSummary(
        split=export.output_split,
        source_id=export.source_id,
        archive=str(export.archive_path),
        video=str(resolved.video.path),
        fps=resolved.video.fps,
        source_frames=resolved.video.frame_count,
        reviewed_frames=len(export.listed_frames),
        selected_frames=len(selected),
        positive_images=len(positives),
        negative_images=len(selected - positives),
        boxes=sum(len(export.labels[frame].splitlines()) for frame in positives),
        clipped_boxes=export.clipped_boxes,
        frame_count_delta=resolved.frame_count_delta,
        frame_count_drift=resolved.frame_count_drift,
    )


def _manifest_payload(
    resolved: list[ResolvedClip], excluded: list[dict[str, str]]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "resolved_clips": [
            {
                "split": item.export.output_split,
                "source_id": item.export.source_id,
                "archive": str(item.export.archive_path),
                "video": str(item.video.path),
                "reviewed_frames": len(item.export.listed_frames),
                "labeled_frames": len(item.export.labels),
                "boxes": item.export.box_count,
                "frame_count_delta": item.frame_count_delta,
                "frame_count_drift": item.frame_count_drift,
            }
            for item in resolved
        ],
        "excluded_exports": excluded,
    }


def _summary_payload(
    summaries: list[ClipSummary],
    excluded: list[dict[str, str]],
    positive_fps: float,
    background_fps: float,
    jpeg_quality: int,
) -> dict[str, object]:
    totals: dict[str, dict[str, int]] = {}
    for split in ("train", "val", "test"):
        rows = [item for item in summaries if item.split == split]
        totals[split] = {
            "clips": len(rows),
            "source_vods": len({item.source_id for item in rows}),
            "images": sum(item.selected_frames for item in rows),
            "positive_images": sum(item.positive_images for item in rows),
            "negative_images": sum(item.negative_images for item in rows),
            "boxes": sum(item.boxes for item in rows),
        }
    return {
        "schema_version": 1,
        "positive_fps": positive_fps,
        "background_fps": background_fps,
        "jpeg_quality": jpeg_quality,
        "totals": totals,
        "excluded_exports": excluded,
        "clips": [asdict(item) for item in summaries],
    }


def main() -> None:
    args = parse_args()
    if args.positive_fps <= 0 or args.background_fps <= 0:
        raise ValueError("--positive-fps and --background-fps must be positive")
    if not 1 <= args.jpeg_quality <= 100:
        raise ValueError("--jpeg-quality must be between 1 and 100")
    if not 0 < args.max_frame_drift < 1:
        raise ValueError("--max-frame-drift must be between 0 and 1")
    if args.output.exists() and not args.dry_run:
        raise FileExistsError(
            f"Output already exists: {args.output}. Choose a new path to avoid overwriting it."
        )

    resolved, excluded = resolve_plan(
        args.exports_root,
        args.staging_root,
        args.legacy_vod01_root,
        args.max_frame_drift,
    )
    manifest = _manifest_payload(resolved, excluded)
    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return

    args.output.mkdir(parents=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    summaries: list[ClipSummary] = []
    for item in resolved:
        print(
            f"Preparing {item.export.archive_path.name} -> "
            f"{item.video.path.name} ({item.export.output_split})",
            flush=True,
        )
        summaries.append(
            prepare_clip(
                item,
                args.output,
                args.positive_fps,
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
    summary = _summary_payload(
        summaries,
        excluded,
        args.positive_fps,
        args.background_fps,
        args.jpeg_quality,
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["totals"], indent=2))


if __name__ == "__main__":
    main()
