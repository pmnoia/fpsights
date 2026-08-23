"""Lightweight Valorant round segmentation.

The segmenter samples two stable HUD areas: the top-center round timer and the
``BUY PHASE`` banner.  It returns timestamps into the original video; it never
re-encodes or cuts the source VOD.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2 as cv
import numpy as np


class Phase(str, Enum):
    NON_GAMEPLAY = "non_gameplay"
    BUY = "buy"
    LIVE = "live"
    ROUND_END = "round_end"


@dataclass(frozen=True)
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_ms: int


@dataclass(frozen=True)
class Observation:
    timestamp_ms: int
    hud_confidence: float
    buy_confidence: float
    timer_prefix: str | None


@dataclass(frozen=True)
class Segment:
    id: str
    phase: Phase
    start_ms: int
    end_ms: int
    analyze: bool
    confidence: float
    round_number: int | None = None
    partial: bool = False

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["phase"] = self.phase.value
        payload["duration_ms"] = self.duration_ms
        return payload


@dataclass(frozen=True)
class SegmentationConfig:
    sample_rate: float = 2.0
    minimum_gameplay_seconds: float = 3.0
    maximum_hud_gap_seconds: float = 3.0
    maximum_buy_gap_seconds: float = 15.0
    minimum_buy_seconds: float = 5.0
    round_end_seconds: float = 6.0
    minimum_buy_hits: int = 2

    def validate(self) -> None:
        non_negative = {
            "minimum_gameplay_seconds": self.minimum_gameplay_seconds,
            "maximum_hud_gap_seconds": self.maximum_hud_gap_seconds,
            "maximum_buy_gap_seconds": self.maximum_buy_gap_seconds,
            "minimum_buy_seconds": self.minimum_buy_seconds,
            "round_end_seconds": self.round_end_seconds,
        }
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        for name, value in non_negative.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.minimum_buy_hits < 1:
            raise ValueError("minimum_buy_hits must be at least one")


@dataclass(frozen=True)
class _RoundAnchor:
    buy_start_ms: int
    live_start_ms: int
    confidence: float
    timer_confirmed: bool


def probe_video(video_path: str | Path) -> VideoInfo:
    """Read the video metadata required by the pipeline."""
    path = Path(video_path)
    video = cv.VideoCapture(str(path))
    if not video.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")

    try:
        width = int(round(video.get(cv.CAP_PROP_FRAME_WIDTH)))
        height = int(round(video.get(cv.CAP_PROP_FRAME_HEIGHT)))
        fps = float(video.get(cv.CAP_PROP_FPS))
        frame_count = int(round(video.get(cv.CAP_PROP_FRAME_COUNT)))
    finally:
        video.release()

    if width < 1 or height < 1 or fps <= 0 or frame_count < 1:
        raise ValueError(f"Video has invalid metadata: {path}")
    return VideoInfo(
        path=str(path),
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_ms=int(round(frame_count / fps * 1000)),
    )


def scan_video(
    video_path: str | Path,
    config: SegmentationConfig | None = None,
) -> tuple[VideoInfo, list[Observation]]:
    """Sample a VOD and collect inexpensive HUD observations."""
    config = config or SegmentationConfig()
    config.validate()
    info = probe_video(video_path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        return info, _scan_with_ffmpeg(ffmpeg, Path(video_path), info, config)
    return info, _scan_with_opencv(Path(video_path), info, config)


def _scan_with_ffmpeg(
    ffmpeg: str,
    video_path: Path,
    info: VideoInfo,
    config: SegmentationConfig,
) -> list[Observation]:
    """Decode sampled, half-size frames through FFmpeg's native pipeline."""
    width = min(info.width, 864)
    height = max(2, round(info.height * width / info.width / 2) * 2)
    frame_size = width * height * 3
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-an",
        "-vf",
        f"fps={config.sample_rate},scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    observations: list[Observation] = []
    try:
        while frame_bytes := _read_exact(process.stdout, frame_size):
            frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(
                height,
                width,
                3,
            )
            timestamp_ms = round(len(observations) / config.sample_rate * 1000)
            observations.append(observe_frame(frame, timestamp_ms))
    except BaseException:
        process.terminate()
        process.wait()
        raise

    error = process.stderr.read().decode("utf-8", errors="replace").strip()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"FFmpeg could not scan {video_path}: {error}")
    return observations


def _read_exact(stream: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks) if len(chunks) == size else b""


def _scan_with_opencv(
    video_path: Path,
    info: VideoInfo,
    config: SegmentationConfig,
) -> list[Observation]:
    """Portable fallback used when FFmpeg is not installed."""
    video = cv.VideoCapture(str(video_path))
    if not video.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    frame_step = max(1, round(info.fps / config.sample_rate))
    observations: list[Observation] = []
    frame_number = 0
    try:
        while video.grab():
            if frame_number % frame_step == 0:
                success, frame = video.retrieve()
                if not success:
                    break
                timestamp_ms = round(frame_number / info.fps * 1000)
                observations.append(observe_frame(frame, timestamp_ms))
            frame_number += 1
    finally:
        video.release()
    return observations


def observe_frame(frame: Any, timestamp_ms: int) -> Observation:
    """Extract the timer and buy-banner signals from one frame."""
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        raise ValueError("observe_frame() received an empty frame")
    hud_confidence, timer_prefix = _timer_signal(frame)
    return Observation(
        timestamp_ms=timestamp_ms,
        hud_confidence=round(hud_confidence, 4),
        buy_confidence=round(_buy_banner_signal(frame), 4),
        timer_prefix=timer_prefix,
    )


def segment_video(
    video_path: str | Path,
    config: SegmentationConfig | None = None,
) -> dict[str, Any]:
    """Create a JSON-friendly segmentation plan for one VOD."""
    config = config or SegmentationConfig()
    info, observations = scan_video(video_path, config)
    return build_analysis_plan(info, observations, config)


def build_analysis_plan(
    video: VideoInfo,
    observations: list[Observation],
    config: SegmentationConfig | None = None,
) -> dict[str, Any]:
    """Turn sampled HUD observations into a gap-free phase timeline."""
    config = config or SegmentationConfig()
    config.validate()
    windows = _gameplay_windows(observations, video.duration_ms, config)
    segments: list[Segment] = []
    cursor_ms = 0
    round_number = 1

    for window_start, window_end in windows:
        if window_start > cursor_ms:
            segments.append(
                _segment(Phase.NON_GAMEPLAY, cursor_ms, window_start, 0.9)
            )
        anchors = _round_anchors(
            observations,
            window_start,
            window_end,
            config,
        )
        window_segments, round_number = _segment_window(
            window_start,
            window_end,
            anchors,
            round_number,
            config,
        )
        segments.extend(window_segments)
        cursor_ms = window_end

    if cursor_ms < video.duration_ms:
        segments.append(
            _segment(Phase.NON_GAMEPLAY, cursor_ms, video.duration_ms, 0.9)
        )

    normalized = _normalize_segments(segments, video.duration_ms)
    numbered = [
        Segment(
            id=f"segment-{index:03d}",
            phase=item.phase,
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            analyze=item.analyze,
            confidence=item.confidence,
            round_number=item.round_number,
            partial=item.partial,
        )
        for index, item in enumerate(normalized, start=1)
    ]
    return _plan_payload(video, config, numbered, len(observations))


def _gameplay_windows(
    observations: list[Observation],
    duration_ms: int,
    config: SegmentationConfig,
) -> list[tuple[int, int]]:
    banner_groups = _buy_banner_groups(observations, config)
    hud_times = [
        item.timestamp_ms for item in observations if item.hud_confidence >= 0.55
    ]
    if not hud_times:
        return []

    margin_ms = round(500 / config.sample_rate)
    if banner_groups:
        # One VOD currently represents one match. Buy anchors bridge brief timer
        # occlusion from scoreboards, effects, and compression artifacts.
        start = max(0, banner_groups[0][0].timestamp_ms - margin_ms)
        after_first_buy = [time for time in hud_times if time >= start]
        end = min(duration_ms, after_first_buy[-1] + margin_ms)
        if duration_ms - end <= 15_000:
            end = duration_ms
        return [(start, end)]

    groups = _group_times(
        hud_times,
        round(config.maximum_hud_gap_seconds * 1000),
    )
    minimum_ms = round(config.minimum_gameplay_seconds * 1000)
    windows = []
    for group in groups:
        start = max(0, group[0] - margin_ms)
        end = min(duration_ms, group[-1] + margin_ms)
        if end - start >= minimum_ms:
            windows.append((start, end))
    return windows


def _round_anchors(
    observations: list[Observation],
    window_start: int,
    window_end: int,
    config: SegmentationConfig,
) -> list[_RoundAnchor]:
    """Create one round anchor per buy phase."""
    window_items = [
        item
        for item in observations
        if window_start <= item.timestamp_ms < window_end
    ]
    banner_groups = _buy_banner_groups(window_items, config)
    margin_ms = round(500 / config.sample_rate)
    anchors: list[_RoundAnchor] = []

    for group in banner_groups:
        buy_start = max(window_start, group[0].timestamp_ms - margin_ms)
        live_start, timer_confirmed = _live_start_after_banner(
            window_items,
            group,
            window_end,
        )
        if live_start - buy_start < round(config.minimum_buy_seconds * 1000):
            continue
        confidence = sum(item.buy_confidence for item in group) / len(group)
        anchors.append(
            _RoundAnchor(buy_start, live_start, confidence, timer_confirmed)
        )

    timer_starts = _timer_live_starts(window_items)
    if not anchors:
        for live_start in timer_starts:
            expected_buy_ms = (
                45_000 if live_start - window_start >= 40_000 else 30_000
            )
            buy_start = max(window_start, live_start - expected_buy_ms)
            if buy_start - window_start <= margin_ms:
                buy_start = window_start
            anchors.append(
                _RoundAnchor(buy_start, live_start, 0.72, True)
            )
        return _deduplicate_anchors(anchors)

    # A combat report or spectator overlay can cover BUY PHASE while leaving
    # the timer readable. Recover timer starts only between two banner anchors;
    # unbounded starts are too easy to confuse with menus at the VOD edges.
    banner_live_starts = sorted(item.live_start_ms for item in anchors)
    for live_start in timer_starts:
        if any(abs(value - live_start) < 5_000 for value in banner_live_starts):
            continue
        bounded = (
            any(value < live_start for value in banner_live_starts)
            and any(value > live_start for value in banner_live_starts)
        )
        if bounded:
            anchors.append(
                _RoundAnchor(
                    max(window_start, live_start - 30_000),
                    live_start,
                    0.72,
                    True,
                )
            )

    return _deduplicate_anchors(anchors)


def _live_start_after_banner(
    observations: list[Observation],
    group: list[Observation],
    window_end: int,
) -> tuple[int, bool]:
    """Use the first stable 1:xx timer after the buy banner disappears."""
    last_banner_ms = group[-1].timestamp_ms
    candidates = [
        item
        for item in observations
        if last_banner_ms < item.timestamp_ms <= group[0].timestamp_ms + 50_000
    ]
    for first, second in zip(candidates, candidates[1:]):
        if first.timer_prefix == second.timer_prefix == "one":
            return first.timestamp_ms, True
    sample_interval_ms = (
        observations[1].timestamp_ms - observations[0].timestamp_ms
        if len(observations) > 1
        else 500
    )
    return min(window_end, last_banner_ms + sample_interval_ms), False


def _buy_banner_groups(
    observations: list[Observation],
    config: SegmentationConfig,
) -> list[list[Observation]]:
    candidates = [
        item
        for item in observations
        if item.hud_confidence >= 0.55 and item.buy_confidence >= 0.55
    ]
    if not candidates:
        return []
    groups = _group_items(
        candidates,
        round(config.maximum_buy_gap_seconds * 1000),
    )
    return [
        group
        for group in groups
        if len(group) >= config.minimum_buy_hits
        or max(item.buy_confidence for item in group) >= 0.8
    ]


def _timer_live_starts(observations: list[Observation]) -> list[int]:
    """Find stable timer transitions from 0:xx to 1:xx."""
    armed = False
    zero_start: int | None = None
    one_streak: list[int] = []
    starts: list[int] = []

    for item in observations:
        if item.hud_confidence < 0.55 or item.timer_prefix is None:
            one_streak.clear()
            continue
        if item.timer_prefix == "zero":
            zero_start = zero_start if zero_start is not None else item.timestamp_ms
            armed = item.timestamp_ms - zero_start >= 1_500 or armed
            one_streak.clear()
            continue
        zero_start = None
        if not armed:
            continue
        one_streak.append(item.timestamp_ms)
        if len(one_streak) == 2:
            starts.append(one_streak[0])
            armed = False
            one_streak.clear()
    return starts


def _deduplicate_anchors(anchors: list[_RoundAnchor]) -> list[_RoundAnchor]:
    deduplicated: list[_RoundAnchor] = []
    for anchor in sorted(anchors, key=lambda item: item.live_start_ms):
        if deduplicated and anchor.live_start_ms - deduplicated[-1].live_start_ms < 5_000:
            previous = deduplicated[-1]
            deduplicated[-1] = _RoundAnchor(
                buy_start_ms=min(previous.buy_start_ms, anchor.buy_start_ms),
                live_start_ms=max(previous.live_start_ms, anchor.live_start_ms),
                confidence=max(previous.confidence, anchor.confidence),
                timer_confirmed=previous.timer_confirmed or anchor.timer_confirmed,
            )
        else:
            deduplicated.append(anchor)
    return deduplicated


def _segment_window(
    window_start: int,
    window_end: int,
    anchors: list[_RoundAnchor],
    first_round_number: int,
    config: SegmentationConfig,
) -> tuple[list[Segment], int]:
    if not anchors:
        return [
            _segment(
                Phase.LIVE,
                window_start,
                window_end,
                0.55,
                round_number=first_round_number,
                partial=True,
            )
        ], first_round_number + 1

    segments: list[Segment] = []
    round_number = first_round_number
    first_buy = anchors[0].buy_start_ms
    if first_buy > window_start:
        round_end_start = max(
            window_start,
            first_buy - round(config.round_end_seconds * 1000),
        )
        if round_end_start > window_start:
            segments.append(
                _segment(
                    Phase.LIVE,
                    window_start,
                    round_end_start,
                    0.55,
                    round_number=round_number,
                    partial=True,
                )
            )
        if first_buy > round_end_start:
            segments.append(
                _segment(
                    Phase.ROUND_END,
                    round_end_start,
                    first_buy,
                    0.55,
                    round_number=round_number,
                    partial=True,
                )
            )
        round_number += 1

    for index, anchor in enumerate(anchors):
        next_buy = (
            anchors[index + 1].buy_start_ms
            if index + 1 < len(anchors)
            else window_end
        )
        live_start = min(anchor.live_start_ms, window_end)
        segments.append(
            _segment(
                Phase.BUY,
                anchor.buy_start_ms,
                live_start,
                anchor.confidence,
                round_number=round_number,
                partial=live_start >= window_end,
            )
        )
        if live_start < window_end:
            round_end_start = (
                max(
                    live_start,
                    next_buy - round(config.round_end_seconds * 1000),
                )
                if index + 1 < len(anchors)
                else window_end
            )
            if round_end_start > live_start:
                segments.append(
                    _segment(
                        Phase.LIVE,
                        live_start,
                        round_end_start,
                        0.9 if anchor.timer_confirmed else 0.65,
                        round_number=round_number,
                        partial=index + 1 == len(anchors),
                    )
                )
            if index + 1 < len(anchors) and next_buy > round_end_start:
                segments.append(
                    _segment(
                        Phase.ROUND_END,
                        round_end_start,
                        next_buy,
                        0.7,
                        round_number=round_number,
                    )
                )
        round_number += 1
    return segments, round_number


def _timer_signal(frame: Any) -> tuple[float, str | None]:
    roi = _crop(frame, 0.47, 0.015, 0.53, 0.08)
    if roi.size == 0:
        return 0.0, None
    gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
    threshold = int(min(245, max(170, gray.mean() + 0.75 * gray.std())))
    _, mask = cv.threshold(gray, threshold, 255, cv.THRESH_BINARY)
    count, _, stats, _ = cv.connectedComponentsWithStats(mask)
    height, width = mask.shape
    candidates = []
    for x, y, component_width, component_height, area in stats[1:count]:
        if not 0.04 * width <= x <= 0.34 * width:
            continue
        if not 0.10 * height <= y <= 0.48 * height:
            continue
        if not 0.26 * height <= component_height <= 0.62 * height:
            continue
        if not 0.04 * width <= component_width <= 0.27 * width:
            continue
        if area >= 0.006 * width * height:
            candidates.append((x, component_width, component_height))
    if not candidates:
        return 0.0, None

    x, component_width, component_height = min(candidates)
    prefix = "one" if component_width / component_height < 0.45 else "zero"
    expected_x = 0.23 if prefix == "one" else 0.20
    x_score = max(0.0, 1.0 - abs(x / width - expected_x) / 0.18)
    height_score = max(
        0.0,
        1.0 - abs(component_height / height - 0.41) / 0.28,
    )
    return min(1.0, 0.55 + 0.225 * (x_score + height_score)), prefix


def _buy_banner_signal(frame: Any) -> float:
    roi = _crop(frame, 0.39, 0.14, 0.61, 0.235)
    if roi.size == 0:
        return 0.0
    hsv = cv.cvtColor(roi, cv.COLOR_BGR2HSV)
    mask = cv.inRange(hsv, (0, 0, 175), (179, 105, 255))
    mask = cv.morphologyEx(mask, cv.MORPH_OPEN, np.ones((2, 2), np.uint8))
    count, _, stats, _ = cv.connectedComponentsWithStats(mask)
    height, width = mask.shape
    letters = []
    for x, y, component_width, component_height, area in stats[1:count]:
        aspect_ratio = component_width / component_height
        valid = (
            0.035 * width <= component_width <= 0.20 * width
            and 0.35 * height <= component_height <= 0.78 * height
            and 0.18 <= aspect_ratio <= 1.35
            and area >= 0.002 * width * height
        )
        if valid:
            letters.append((x, y, component_width, component_height))

    best_aligned = []
    for letter in letters:
        center_y = letter[1] + letter[3] / 2
        aligned = [
            candidate
            for candidate in letters
            if abs(candidate[1] + candidate[3] / 2 - center_y) <= 0.14 * height
            and 0.65 <= candidate[3] / letter[3] <= 1.5
        ]
        if len(aligned) > len(best_aligned):
            best_aligned = aligned

    expected_positions = (0.179, 0.261, 0.337, 0.450, 0.529, 0.611, 0.695, 0.774)
    actual_positions = [letter[0] / width for letter in best_aligned]
    matched = sum(
        any(abs(actual - expected) <= 0.036 for actual in actual_positions)
        for expected in expected_positions
    )
    return min(1.0, matched / 6)


def _crop(frame: Any, x1: float, y1: float, x2: float, y2: float) -> Any:
    height, width = frame.shape[:2]
    return frame[
        round(y1 * height) : round(y2 * height),
        round(x1 * width) : round(x2 * width),
    ]


def _group_times(times: list[int], maximum_gap_ms: int) -> list[list[int]]:
    if not times:
        return []
    groups = [[times[0]]]
    for timestamp_ms in times[1:]:
        if timestamp_ms - groups[-1][-1] > maximum_gap_ms:
            groups.append([])
        groups[-1].append(timestamp_ms)
    return groups


def _group_items(
    observations: list[Observation],
    maximum_gap_ms: int,
) -> list[list[Observation]]:
    if not observations:
        return []
    groups = [[observations[0]]]
    for item in observations[1:]:
        if item.timestamp_ms - groups[-1][-1].timestamp_ms > maximum_gap_ms:
            groups.append([])
        groups[-1].append(item)
    return groups


def _segment(
    phase: Phase,
    start_ms: int,
    end_ms: int,
    confidence: float,
    *,
    round_number: int | None = None,
    partial: bool = False,
) -> Segment:
    return Segment(
        id="",
        phase=phase,
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        analyze=phase == Phase.LIVE,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        round_number=round_number,
        partial=partial,
    )


def _normalize_segments(segments: list[Segment], duration_ms: int) -> list[Segment]:
    """Remove empty intervals and guarantee a gap-free timeline."""
    normalized: list[Segment] = []
    cursor = 0
    for item in sorted(segments, key=lambda value: (value.start_ms, value.end_ms)):
        start = max(cursor, max(0, item.start_ms))
        end = min(duration_ms, item.end_ms)
        if start > cursor:
            normalized.append(_segment(Phase.NON_GAMEPLAY, cursor, start, 0.7))
        if end <= start:
            continue
        normalized.append(
            Segment(
                id=item.id,
                phase=item.phase,
                start_ms=start,
                end_ms=end,
                analyze=item.analyze,
                confidence=item.confidence,
                round_number=item.round_number,
                partial=item.partial,
            )
        )
        cursor = end
    if cursor < duration_ms:
        normalized.append(_segment(Phase.NON_GAMEPLAY, cursor, duration_ms, 0.7))
    return normalized


def _plan_payload(
    video: VideoInfo,
    config: SegmentationConfig,
    segments: list[Segment],
    observation_count: int,
) -> dict[str, Any]:
    live_segments = [item for item in segments if item.analyze]
    round_numbers = {
        item.round_number for item in segments if item.round_number is not None
    }
    return {
        "schema_version": 1,
        "video": asdict(video),
        "config": asdict(config),
        "summary": {
            "rounds": len(round_numbers),
            "segments": len(segments),
            "observation_count": observation_count,
            "analyzable_duration_ms": sum(item.duration_ms for item in live_segments),
            "discarded_duration_ms": sum(
                item.duration_ms
                for item in segments
                if item.phase == Phase.NON_GAMEPLAY
            ),
            "low_confidence_segments": sum(
                item.confidence < 0.7 for item in segments
            ),
        },
        "segments": [item.to_dict() for item in segments],
        "analysis_ranges": [
            {
                "segment_id": item.id,
                "round_number": item.round_number,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
            }
            for item in live_segments
        ],
    }
