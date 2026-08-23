from __future__ import annotations

import json
from pathlib import Path

import cv2 as cv
import numpy as np
import pytest

from src.pipeline.processor import (
    ProcessingConfig,
    load_analysis_plan,
    process_video,
)


def _write_test_video(path: Path) -> None:
    writer = cv.VideoWriter(
        str(path),
        cv.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (64, 48),
    )
    assert writer.isOpened()
    try:
        for value in range(30):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
    finally:
        writer.release()


class _FakeDetector:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def detect(self, _frame) -> dict:
        return {
            "crosshair_x": 32,
            "crosshair_y": 24,
            "enemy_positions": [],
        }


def _write_plan(path: Path, video_path: Path, ranges: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "video": {"path": str(video_path)},
                "summary": {
                    "rounds": len(ranges),
                    "segments": len(ranges),
                    "observation_count": 0,
                    "analyzable_duration_ms": sum(
                        item["end_ms"] - item["start_ms"] for item in ranges
                    ),
                    "discarded_duration_ms": 0,
                    "low_confidence_segments": 0,
                },
                "segments": [],
                "analysis_ranges": ranges,
            }
        ),
        encoding="utf-8",
    )


def test_segmentation_only_is_ready_before_model_training(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "vod.mp4"
    plan_path = tmp_path / "reviewed.json"
    output_dir = tmp_path / "output"
    _write_test_video(video_path)
    _write_plan(plan_path, video_path, [])

    result = process_video(
        ProcessingConfig(
            video_path=video_path,
            output_dir=output_dir,
            segments_path=plan_path,
        )
    )

    assert result["status"] == "segmented"
    assert result["detection"] is None
    assert (output_dir / "segments.json").is_file()
    assert (output_dir / "run.json").is_file()
    assert not (output_dir / "detections.json").exists()
    assert not (output_dir / "metrics.json").exists()


def test_yolo_processes_only_live_ranges_and_writes_review_video(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "vod.mp4"
    plan_path = tmp_path / "segments.json"
    output_dir = tmp_path / "output"
    _write_test_video(video_path)
    _write_plan(
        plan_path,
        video_path,
        [
            {
                "segment_id": "segment-002",
                "round_number": 1,
                "start_ms": 1_000,
                "end_ms": 2_000,
            }
        ],
    )

    result = process_video(
        ProcessingConfig(
            video_path=video_path,
            output_dir=output_dir,
            model_path=tmp_path / "unused.pt",
            segments_path=plan_path,
            frame_skip=1,
            review_video=True,
        ),
        detector_factory=_FakeDetector,
    )

    payload = json.loads(
        (output_dir / "detections.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "complete"
    assert payload["processed_frames"] == 10
    assert [frame["frame_number"] for frame in payload["frames"]] == list(
        range(10, 20)
    )
    assert {frame["round_number"] for frame in payload["frames"]} == {1}
    assert payload["frames"][0]["timestamp_ms"] == 1_000
    assert (output_dir / "review.mp4").stat().st_size > 0
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["summary"]["crosshair"]["evaluated_frames"] == 0
    assert result["artifacts"]["metrics"].endswith("metrics.json")


def test_manifest_rejects_a_different_video(tmp_path: Path) -> None:
    plan_path = tmp_path / "segments.json"
    _write_plan(plan_path, Path("first.mp4"), [])

    with pytest.raises(ValueError, match="different video"):
        load_analysis_plan(plan_path, Path("second.mp4"))


def test_manifest_rejects_overlapping_ranges(tmp_path: Path) -> None:
    plan_path = tmp_path / "segments.json"
    video_path = Path("vod.mp4")
    _write_plan(
        plan_path,
        video_path,
        [
            {"start_ms": 1_000, "end_ms": 2_000},
            {"start_ms": 1_500, "end_ms": 2_500},
        ],
    )

    with pytest.raises(ValueError, match="sorted and non-overlapping"):
        load_analysis_plan(plan_path, video_path)


def test_manifest_rejects_a_range_beyond_video_duration(tmp_path: Path) -> None:
    plan_path = tmp_path / "segments.json"
    video_path = Path("vod.mp4")
    _write_plan(
        plan_path,
        video_path,
        [{"start_ms": 9_000, "end_ms": 11_000}],
    )

    with pytest.raises(ValueError, match="exceeds the video duration"):
        load_analysis_plan(plan_path, video_path, 10_000)
