"""Command-line entry point for YOLO inference on a gameplay video."""

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2 as cv

from .pipeline.detector import YoloDetector, draw_detections
from .pipeline.frame_reader import read_frames


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run trained YOLO enemy detection on an FPS gameplay video."
    )
    parser.add_argument("--input", type=Path, required=True, help="Input video path")
    parser.add_argument("--model", type=Path, required=True, help="Trained .pt weights")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Minimum YOLO confidence (default: 0.25)",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=5,
        help="Process every Nth frame (default: 5)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional limit on processed frames",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Ultralytics device such as cpu, mps, or 0",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show detections while processing; press q to stop",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    detector = YoloDetector(args.model, args.confidence, args.device)
    frames = []

    try:
        for frame_number, frame in read_frames(
            args.input,
            frame_skip=args.frame_skip,
            max_frames=args.max_frames,
        ):
            detection = detector.detect(frame)
            frames.append({"frame_number": frame_number, **detection})

            if args.preview:
                cv.imshow("FPSights YOLO Detection", draw_detections(frame, detection))
                if cv.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        if args.preview:
            cv.destroyAllWindows()

    payload = {
        "video": str(args.input),
        "model": str(args.model),
        "confidence_threshold": args.confidence,
        "frame_skip": args.frame_skip,
        "processed_frames": len(frames),
        "frames": frames,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Processed {len(frames)} frames. Results saved to {args.output}")


if __name__ == "__main__":
    main()
