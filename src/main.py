"""Simple command-line entry point for FPSights video processing."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .pipeline.processor import ProcessingConfig, process_video


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment a Valorant VOD and optionally run YOLO detection."
    )
    parser.add_argument("input", type=Path, help="Input .mp4 or .mkv video")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Artifact directory (default: output/<video-name>)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        help="Optional trained YOLO .pt weights; omit while labeling in CVAT",
    )
    parser.add_argument(
        "--segments",
        type=Path,
        help="Optional reviewed segments.json; otherwise segmentation runs first",
    )
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--frame-skip", type=int, default=5)
    parser.add_argument("--sample-rate", type=float, default=2.0)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--device", help="Ultralytics device: cpu, mps, or 0")
    parser.add_argument(
        "--review-video",
        action="store_true",
        help="Save a compact annotated video of analyzed live rounds",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show detections while processing; press q to stop",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    output_dir = args.output_dir or Path("output") / args.input.stem
    config = ProcessingConfig(
        video_path=args.input,
        output_dir=output_dir,
        model_path=args.model,
        segments_path=args.segments,
        confidence=args.confidence,
        frame_skip=args.frame_skip,
        sample_rate=args.sample_rate,
        max_frames=args.max_frames,
        device=args.device,
        preview=args.preview,
        review_video=args.review_video,
    )

    if args.model is None:
        print("Creating gameplay segments (YOLO will be skipped)...")
    else:
        print("Preparing gameplay segments, then running YOLO...")

    result = process_video(config, progress=_print_progress)
    summary = result["segmentation"]
    print(
        f"Segments ready: {summary['rounds']} rounds, "
        f"{summary['analyzable_duration_ms'] / 1000:.1f}s of live gameplay."
    )
    if result["detection"] is None:
        print(f"Add --model models/best.pt when training is done. Output: {output_dir}")
    else:
        detection = result["detection"]
        print(
            f"YOLO complete: {detection['processed_frames']} frames, "
            f"{detection['total_detections']} detections. Output: {output_dir}"
        )


def _print_progress(done: int, total: int) -> None:
    if done == 1 or done == total or done % 250 == 0:
        print(f"Processed {done}/{total} YOLO frames")


if __name__ == "__main__":
    main()
