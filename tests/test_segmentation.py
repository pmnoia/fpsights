from __future__ import annotations

import cv2 as cv
import numpy as np

from src.pipeline.segmentation import (
    Observation,
    Phase,
    SegmentationConfig,
    VideoInfo,
    build_analysis_plan,
    scan_video,
)


def _observation(
    timestamp_ms: int,
    *,
    hud: bool = True,
    buy: bool = False,
    prefix: str | None = "zero",
) -> Observation:
    return Observation(
        timestamp_ms=timestamp_ms,
        hud_confidence=0.95 if hud else 0.0,
        buy_confidence=0.95 if buy else 0.0,
        timer_prefix=prefix if hud else None,
    )


def test_scan_samples_at_configured_rate(tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    writer = cv.VideoWriter(
        str(video_path),
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

    _, observations = scan_video(
        video_path,
        SegmentationConfig(sample_rate=2.0),
    )

    assert [item.timestamp_ms for item in observations] == [
        0,
        500,
        1_000,
        1_500,
        2_000,
        2_500,
    ]


def test_builds_gap_free_round_timeline() -> None:
    observations = []
    for timestamp_ms in range(0, 120_000, 500):
        if timestamp_ms < 5_000 or timestamp_ms >= 105_000:
            observations.append(_observation(timestamp_ms, hud=False, prefix=None))
        elif timestamp_ms < 25_000:
            observations.append(_observation(timestamp_ms, buy=True, prefix="zero"))
        elif timestamp_ms < 75_000:
            prefix = "one" if timestamp_ms < 60_000 else "zero"
            observations.append(_observation(timestamp_ms, prefix=prefix))
        elif timestamp_ms < 95_000:
            observations.append(_observation(timestamp_ms, buy=True, prefix="zero"))
        else:
            observations.append(_observation(timestamp_ms, prefix="one"))

    video = VideoInfo("synthetic.mp4", 1920, 1080, 60.0, 7200, 120_000)
    plan = build_analysis_plan(video, observations)
    segments = plan["segments"]

    assert segments[0]["phase"] == Phase.NON_GAMEPLAY.value
    assert plan["summary"]["rounds"] == 2
    assert len(plan["analysis_ranges"]) == 2
    assert segments[-1]["phase"] == Phase.NON_GAMEPLAY.value
    assert segments[0]["start_ms"] == 0
    assert segments[-1]["end_ms"] == video.duration_ms
    assert all(
        left["end_ms"] == right["start_ms"]
        for left, right in zip(segments, segments[1:])
    )
    assert all(segment["duration_ms"] > 0 for segment in segments)


def test_no_hud_becomes_non_gameplay() -> None:
    video = VideoInfo("menu.mp4", 1920, 1080, 60.0, 600, 10_000)
    observations = [
        _observation(timestamp_ms, hud=False, prefix=None)
        for timestamp_ms in range(0, 10_000, 500)
    ]

    plan = build_analysis_plan(video, observations)

    assert plan["summary"]["rounds"] == 0
    assert plan["summary"]["discarded_duration_ms"] == 10_000
    assert plan["analysis_ranges"] == []
    assert [item["phase"] for item in plan["segments"]] == ["non_gameplay"]


def test_short_hud_dropout_does_not_split_gameplay() -> None:
    observations = []
    for timestamp_ms in range(0, 20_000, 500):
        hud = not 8_000 <= timestamp_ms <= 9_000
        observations.append(_observation(timestamp_ms, hud=hud, prefix="one"))

    video = VideoInfo("dropout.mp4", 1920, 1080, 60.0, 1200, 20_000)
    plan = build_analysis_plan(
        video,
        observations,
        SegmentationConfig(maximum_hud_gap_seconds=3.0),
    )

    assert plan["summary"]["rounds"] == 1
    assert len(plan["analysis_ranges"]) == 1
    assert plan["analysis_ranges"][0]["start_ms"] == 0


def test_duplicate_buy_banner_clusters_become_one_round_anchor() -> None:
    observations = []
    for timestamp_ms in range(20_000, 100_000, 500):
        first_buy_cluster = 20_000 <= timestamp_ms <= 22_000
        second_buy_cluster = 30_000 <= timestamp_ms <= 34_000
        next_buy = 70_000 <= timestamp_ms < 80_000
        buy = first_buy_cluster or second_buy_cluster or next_buy
        prefix = "one" if 40_000 <= timestamp_ms < 70_000 or timestamp_ms >= 85_000 else "zero"
        observations.append(_observation(timestamp_ms, buy=buy, prefix=prefix))

    video = VideoInfo("duplicate.mp4", 1920, 1080, 60.0, 6000, 100_000)
    plan = build_analysis_plan(video, observations)

    buy_segments = [item for item in plan["segments"] if item["phase"] == "buy"]
    assert plan["summary"]["rounds"] == 2
    assert len(buy_segments) == 2


def test_loading_screen_text_does_not_become_a_buy_phase() -> None:
    observations = []
    for timestamp_ms in range(0, 80_000, 500):
        if timestamp_ms < 20_000:
            observations.append(
                Observation(timestamp_ms, 0.0, 0.95, None)
            )
        elif timestamp_ms < 65_000:
            observations.append(_observation(timestamp_ms, prefix="zero"))
        else:
            observations.append(_observation(timestamp_ms, prefix="one"))

    video = VideoInfo("opening.mp4", 1280, 800, 60.0, 4800, 80_000)
    plan = build_analysis_plan(video, observations)

    assert plan["summary"]["rounds"] == 1
    assert plan["segments"][0]["phase"] == "non_gameplay"
    assert [
        item["phase"] for item in plan["segments"] if item["round_number"] == 1
    ] == ["buy", "live"]


def test_timer_recovers_a_buy_banner_hidden_by_an_overlay() -> None:
    observations = []
    for timestamp_ms in range(0, 180_000, 500):
        first_buy = timestamp_ms < 20_000
        third_buy = 120_000 <= timestamp_ms < 140_000
        timer_prefix = (
            "zero"
            if first_buy
            or 60_000 <= timestamp_ms < 80_000
            or third_buy
            else "one"
        )
        observations.append(
            _observation(
                timestamp_ms,
                buy=first_buy or third_buy,
                prefix=timer_prefix,
            )
        )

    video = VideoInfo("overlay.mp4", 1920, 1080, 60.0, 10_800, 180_000)
    plan = build_analysis_plan(video, observations)
    buy_segments = [
        item for item in plan["segments"] if item["phase"] == "buy"
    ]

    assert plan["summary"]["rounds"] == 3
    assert len(buy_segments) == 3
    assert buy_segments[1]["start_ms"] == 50_000
    assert buy_segments[1]["end_ms"] == 80_000
