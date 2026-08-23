"""Command-line entry point for pre-analysis VOD segmentation."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from .pipeline.segmentation import SegmentationConfig, segment_video


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment a Valorant VOD into buy, live, round-end, and non-gameplay phases."
    )
    parser.add_argument("--input", type=Path, required=True, help="Input video path")
    parser.add_argument("--output", type=Path, required=True, help="Timeline JSON path")
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=2.0,
        help="Frames sampled per second during the lightweight scan (default: 2)",
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=None,
        help="Optionally export each live-round interval with ffmpeg stream copy",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = SegmentationConfig(sample_rate=args.sample_rate)
    plan = segment_video(args.input, config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    summary = plan["summary"]
    print(
        f"Detected {summary['rounds']} rounds and {len(plan['analysis_ranges'])} "
        f"analysis ranges. Timeline saved to {args.output}"
    )
    if summary["low_confidence_segments"]:
        print(
            f"Review recommended: {summary['low_confidence_segments']} "
            "segments have confidence below 0.70."
        )

    if args.clips_dir is not None:
        exported = export_analysis_clips(args.input, plan, args.clips_dir)
        print(f"Exported {exported} live-round clips to {args.clips_dir}")


def export_analysis_clips(
    video_path: Path,
    plan: dict[str, Any],
    output_dir: Path,
) -> int:
    """Export live ranges without modifying or re-encoding the source VOD."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required for --clips-dir but was not found")

    output_dir.mkdir(parents=True, exist_ok=True)
    ranges = plan.get("analysis_ranges", [])
    for index, interval in enumerate(ranges, start=1):
        start_seconds = interval["start_ms"] / 1000
        duration_seconds = (interval["end_ms"] - interval["start_ms"]) / 1000
        round_number = interval.get("round_number") or index
        output_path = output_dir / f"round-{round_number:03d}-live.mp4"
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration_seconds:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-y",
            str(output_path),
        ]
        subprocess.run(command, check=True)

    return len(ranges)


if __name__ == "__main__":
    main()
