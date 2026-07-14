"""Run enemy detection and reaction-time analysis on one recorded video."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2

from src.analysis.enemy_detector import EnemyDetector
from src.analysis.reaction_time import ReactionEvent, ReactionTimeCalculator


def analyze_video(
    video_path: Path,
    detector: Any,
    *,
    reaction_calculator: ReactionTimeCalculator | None = None,
    batch_size: int = 1,
) -> dict[str, object]:
    """Analyze every frame and return a small JSON-compatible result."""

    video_path = video_path.expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video does not exist: {video_path}")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"OpenCV could not open video: {video_path}")

    calculator = reaction_calculator or ReactionTimeCalculator()
    events: list[ReactionEvent] = []

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or width <= 0 or height <= 0:
            raise ValueError(
                f"Video metadata is invalid: fps={fps}, size={width}x{height}"
            )

        frame_index = 0
        while True:
            frames = []
            for _ in range(batch_size):
                success, frame = capture.read()
                if not success:
                    break
                frames.append(frame)
            if not frames:
                break

            if batch_size > 1 and hasattr(detector, "detect_batch"):
                detection_batches = detector.detect_batch(frames)
                if len(detection_batches) != len(frames):
                    raise RuntimeError(
                        "detector returned a different number of batches than frames"
                    )
            else:
                detection_batches = [detector.detect(frame) for frame in frames]

            for detections in detection_batches:
                timestamp_ms = round(frame_index * 1000 / fps)
                event = calculator.update(
                    timestamp_ms,
                    detections,
                    (width, height),
                )
                if event is not None:
                    events.append(event)
                frame_index += 1

        final_event = calculator.finish()
        if final_event is not None:
            events.append(final_event)

        return {
            "video": str(video_path),
            "fps": fps,
            "frame_width": width,
            "frame_height": height,
            "frames_processed": frame_index,
            "reaction_events": [asdict(event) for event in events],
        }
    finally:
        capture.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze enemy encounters in a recorded gameplay video."
    )
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--batch-size", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    detector = EnemyDetector(args.model, confidence=args.confidence)
    result = analyze_video(args.video, detector, batch_size=args.batch_size)

    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Processed {result['frames_processed']} frames")
    print(f"Reaction events: {len(result['reaction_events'])}")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
