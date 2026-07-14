"""Command-line entry point for enemy-dataset preparation."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.dataset.enemy_dataset import (
    create_dataset_layout,
    sample_video_frames,
    write_sampling_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a one-class Ultralytics enemy dataset."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the dataset layout")
    init_parser.add_argument("--root", type=Path, required=True)
    init_parser.add_argument("--overwrite-yaml", action="store_true")

    extract_parser = subparsers.add_parser(
        "extract", help="Sample frames into raw/images and update the manifest"
    )
    extract_parser.add_argument("--root", type=Path, required=True)
    extract_parser.add_argument("--video", type=Path, required=True)
    extract_parser.add_argument("--interval-seconds", type=float, default=1.0)
    extract_parser.add_argument("--start-seconds", type=float, default=0.0)
    extract_parser.add_argument("--end-seconds", type=float)
    extract_parser.add_argument("--jpeg-quality", type=int, default=95)
    extract_parser.add_argument("--overwrite", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    yaml_path = create_dataset_layout(
        args.root,
        overwrite_yaml=getattr(args, "overwrite_yaml", False),
    )

    if args.command == "init":
        print(f"Created dataset layout: {yaml_path.parent}")
        print(f"Dataset config: {yaml_path}")
        return 0

    samples = sample_video_frames(
        args.video,
        yaml_path.parent / "raw" / "images",
        interval_seconds=args.interval_seconds,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
    )
    manifest_path = yaml_path.parent / "sampling_manifest.csv"
    write_sampling_manifest(samples, manifest_path)
    print(f"Extracted {len(samples)} frames")
    print(f"Sampling manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
