"""End-to-end video processing and artifact generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import cv2 as cv

from src.settings import DEFAULT_CONFIDENCE, DEFAULT_FRAME_SKIP, DEFAULT_SAMPLE_RATE, DEFAULT_IMAGE_SIZE

from .analytics import analyze_detections
from .detector import YoloDetector, draw_detections
from .frame_reader import read_frames
from .positioning import MinimapTracker
from .segmentation import SegmentationConfig, probe_video, segment_video
from .tracking import confirm_tracks


@dataclass(frozen=True)
class ProcessingConfig:
    """Options for one FPSights processing run."""

    video_path: Path
    output_dir: Path
    model_path: Path | None = None
    segments_path: Path | None = None
    confidence: float = DEFAULT_CONFIDENCE
    frame_skip: int = DEFAULT_FRAME_SKIP
    sample_rate: float = DEFAULT_SAMPLE_RATE
    max_frames: int | None = None
    device: str | None = None
    preview: bool = False
    review_video: bool = False

    def validate(self) -> None:
        """Reject settings that would make this processing run invalid."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.frame_skip < 1:
            raise ValueError("frame_skip must be at least 1")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if self.max_frames is not None and self.max_frames < 1:
            raise ValueError("max_frames must be at least 1")
        if self.model_path is None and (self.preview or self.review_video):
            raise ValueError("preview and review_video require YOLO model weights")


def process_video(
    config: ProcessingConfig,
    *,
    detector_factory: Callable[..., Any] = YoloDetector,
    progress: Callable[[int, int], None] | None = None,
    status: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Segment a video and optionally run YOLO over its live ranges.

    The output directory contains stable artifact names that the desktop UI can
    consume later: ``segments.json``, ``detections.json``, ``review.mp4``, and
    ``run.json``.  Detection artifacts are only created when a model is given.
    """
    config.validate()
    if config.model_path is not None and not config.model_path.is_file():
        raise FileNotFoundError(f"Could not find YOLO weights: {config.model_path}")
    if status:
        status("Finding live rounds in the video...")
    info = probe_video(config.video_path)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    if config.segments_path is None:
        plan = segment_video(
            config.video_path,
            SegmentationConfig(sample_rate=config.sample_rate),
        )
        segment_source = "generated"
    else:
        plan = load_analysis_plan(
            config.segments_path,
            config.video_path,
            info.duration_ms,
        )
        segment_source = str(config.segments_path)

    segments_output = config.output_dir / "segments.json"
    _write_json(segments_output, plan)

    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_version": 3,
        "inference_image_size": DEFAULT_IMAGE_SIZE,
        "status": "segmented" if config.model_path is None else "processing",
        "video": asdict(info),
        "model": str(config.model_path) if config.model_path else None,
        "segment_source": segment_source,
        "frame_skip": config.frame_skip,
        "limited_run": config.max_frames is not None,
        "artifacts": {
            "segments": str(segments_output),
            "detections": None,
            "metrics": None,
            "review_video": None,
            "positioning": None,
            "heatmap": None,
            "lessons": None,
        },
        "segmentation": plan["summary"],
        "detection": None,
        "analytics": None,
        "lessons": None,
    }

    if config.model_path is None:
        _write_json(config.output_dir / "run.json", result)
        return result

    if status:
        status("Loading the enemy detector...")
    detector = detector_factory(
        config.model_path,
        config.confidence,
        config.device,
    )
    ranges = plan["analysis_ranges"]
    if status:
        status("Detecting enemies in live gameplay...")
    total_frames = _estimated_frame_count(
        ranges,
        info.fps,
        config.frame_skip,
        config.max_frames,
    )
    review_path = config.output_dir / "review.mp4" if config.review_video else None
    writer = _open_review_writer(review_path, info, config.frame_skip)
    frame_results: list[dict[str, Any]] = []
    positioning_points: list[dict[str, Any]] = []
    minimap_tracker = MinimapTracker()
    stopped_by_user = False

    try:
        for interval in ranges:
            remaining = (
                None
                if config.max_frames is None
                else config.max_frames - len(frame_results)
            )
            if remaining is not None and remaining <= 0:
                break

            for frame_number, frame in read_frames(
                config.video_path,
                frame_skip=config.frame_skip,
                max_frames=remaining,
                start_ms=interval["start_ms"],
                end_ms=interval["end_ms"],
            ):
                position = minimap_tracker.observe(frame, interval["segment_id"])
                if position is not None:
                    positioning_points.append(
                        {
                            "frame_number": frame_number,
                            "timestamp_ms": int(round(frame_number / info.fps * 1000)),
                            "segment_id": interval["segment_id"],
                            "round_number": interval["round_number"],
                            **position,
                        }
                    )
                detection = detector.detect(frame)
                record = {
                    "frame_number": frame_number,
                    "timestamp_ms": int(round(frame_number / info.fps * 1000)),
                    "segment_id": interval["segment_id"],
                    "round_number": interval["round_number"],
                    **detection,
                }
                frame_results.append(record)

                if writer is not None or config.preview:
                    annotated = _annotate_frame(frame, record)
                    if writer is not None:
                        writer.write(annotated)
                    if config.preview:
                        cv.imshow("FPSights video processing", annotated)
                        if cv.waitKey(1) & 0xFF == ord("q"):
                            stopped_by_user = True
                            break

                if progress is not None:
                    progress(len(frame_results), total_frames)

            if stopped_by_user:
                break
    finally:
        if writer is not None:
            writer.release()
        if config.preview:
            cv.destroyAllWindows()

    if status:
        status("Building metrics and report...")
    tracking_gap_ms = max(250, round(3 * config.frame_skip / info.fps * 1000))
    frame_results, tracking_summary = confirm_tracks(
        frame_results, max_gap_ms=tracking_gap_ms
    )
    detections_path = config.output_dir / "detections.json"
    detection_summary = _detection_summary(frame_results)
    _write_json(
        detections_path,
        {
            "schema_version": 1,
            "video": str(config.video_path),
            "model": str(config.model_path),
            "confidence_threshold": config.confidence,
            "frame_skip": config.frame_skip,
            "analysis_ranges": ranges,
            "tracking": tracking_summary,
            **detection_summary,
            "frames": frame_results,
        },
    )

    positioning_path = config.output_dir / "positioning.json"
    _write_json(
        positioning_path,
        {
            "schema_version": 1,
            "video": str(config.video_path),
            "coordinate_space": "normalized top-left minimap crop",
            "tracking_subject": "viewed POV; may include spectated teammates",
            "identity_verified": False,
            "sample_count": len(positioning_points),
            "points": positioning_points,
        },
    )
    heatmap_path = config.output_dir / "heatmap.png"
    heatmap_written = minimap_tracker.render(positioning_points, heatmap_path)

    metrics_path = config.output_dir / "metrics.json"
    analytics = analyze_detections(
        frame_results,
        max_gap_ms=tracking_gap_ms,
    )
    analytics["summary"]["detection_quality"] = tracking_summary
    analytics["summary"]["positioning"] = {
        "sample_count": len(positioning_points),
        "coverage_percent": (
            round(len(positioning_points) / len(frame_results) * 100, 1)
            if frame_results
            else 0.0
        ),
    }
    _write_json(
        metrics_path,
        {
            "schema_version": 1,
            "video": str(config.video_path),
            "definitions": {
                "crosshair_score": (
                    "Distance from the crosshair to the estimated head point "
                    "inside temporally confirmed enemy boxes; an estimate, not accuracy."
                ),
                "aim_reaction": (
                    "Time from first confirmed track detection until the crosshair "
                    "enters that target's upper box area, for measured tracks only; "
                    "not shot reaction time."
                ),
                "positioning": (
                    "White POV-marker locations in the top-left minimap crop; "
                    "may include spectated teammates. Identity and alive state are not verified. "
                    "Rotating or centered minimaps do not give fixed map coordinates."
                ),
            },
            **analytics,
        },
    )

    result["status"] = "stopped" if stopped_by_user else "complete"
    result["artifacts"]["detections"] = str(detections_path)
    result["artifacts"]["metrics"] = str(metrics_path)
    result["artifacts"]["review_video"] = (
        str(review_path) if review_path is not None and frame_results else None
    )
    result["artifacts"]["positioning"] = str(positioning_path)
    result["artifacts"]["heatmap"] = str(heatmap_path) if heatmap_written else None
    result["detection"] = detection_summary
    result["detection"]["tracking"] = tracking_summary
    result["analytics"] = analytics["summary"]
    _write_json(config.output_dir / "run.json", result)
    return result


def load_analysis_plan(
    plan_path: Path,
    video_path: Path,
    video_duration_ms: int | None = None,
) -> dict[str, Any]:
    """Read a saved round timeline and check that its live ranges fit this video."""
    if not plan_path.is_file():
        raise FileNotFoundError(f"Could not find segmentation JSON: {plan_path}")

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid segmentation JSON: {plan_path}") from error

    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("Segmentation JSON must use schema_version 1")

    plan_video = plan.get("video")
    if not isinstance(plan_video, dict) or not isinstance(plan_video.get("path"), str):
        raise ValueError("Segmentation JSON is missing video.path")
    if Path(plan_video["path"]).name != video_path.name:
        raise ValueError(
            "Segmentation JSON belongs to a different video: "
            f"{plan_video['path']}"
        )

    ranges = plan.get("analysis_ranges")
    if not isinstance(ranges, list):
        raise ValueError("Segmentation JSON is missing analysis_ranges")

    previous_end = 0
    for index, interval in enumerate(ranges, start=1):
        if not isinstance(interval, dict):
            raise ValueError(f"Analysis range {index} must be an object")
        start_ms = interval.get("start_ms")
        end_ms = interval.get("end_ms")
        valid_times = (
            isinstance(start_ms, int)
            and not isinstance(start_ms, bool)
            and isinstance(end_ms, int)
            and not isinstance(end_ms, bool)
            and start_ms >= 0
            and end_ms > start_ms
        )
        if not valid_times:
            raise ValueError(f"Analysis range {index} has invalid timestamps")
        if start_ms < previous_end:
            raise ValueError("Analysis ranges must be sorted and non-overlapping")
        if video_duration_ms is not None and end_ms > video_duration_ms:
            raise ValueError(f"Analysis range {index} exceeds the video duration")
        interval.setdefault("segment_id", f"range-{index:03d}")
        interval.setdefault("round_number", None)
        previous_end = end_ms

    return plan


def _estimated_frame_count(
    ranges: list[dict[str, Any]],
    fps: float,
    frame_skip: int,
    limit: int | None,
) -> int:
    """Estimate how many sampled live frames the progress bar should expect."""
    count = sum(
        max(0, round((item["end_ms"] - item["start_ms"]) / 1000 * fps))
        for item in ranges
    )
    count = (count + frame_skip - 1) // frame_skip
    return min(count, limit) if limit is not None else count


def _open_review_writer(path: Path | None, info: Any, frame_skip: int) -> Any:
    if path is None:
        return None
    writer = cv.VideoWriter(
        str(path),
        cv.VideoWriter_fourcc(*"mp4v"),
        max(1.0, info.fps / frame_skip),
        (info.width, info.height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create review video: {path}")
    return writer


def _annotate_frame(frame: Any, record: dict[str, Any]) -> Any:
    output = draw_detections(frame, record)
    round_number = record.get("round_number")
    seconds = record["timestamp_ms"] / 1000
    label = f"Round {round_number or '?'} | {seconds:.1f}s"
    cv.putText(
        output,
        label,
        (16, 32),
        cv.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv.LINE_AA,
    )
    return output


def _detection_summary(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Count analyzed frames and the enemy boxes found in them."""
    counts: Counter[str] = Counter()
    frames_with_detections = 0
    total_detections = 0
    for frame in frames:
        boxes = frame["enemy_positions"]
        if boxes:
            frames_with_detections += 1
        total_detections += len(boxes)
        for box in boxes:
            counts[box["class_name"]] += 1
    return {
        "processed_frames": len(frames),
        "frames_with_detections": frames_with_detections,
        "total_detections": total_detections,
        "detections_by_class": dict(sorted(counts.items())),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
