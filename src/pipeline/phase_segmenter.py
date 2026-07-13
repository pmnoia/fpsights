import csv
import math


def load_round_starts(annotation_csv):
    round_starts = []

    if annotation_csv is None:
        return round_starts

    with open(annotation_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("event_type") != "round_start":
                continue

            round_starts.append({
                "frame_number": int(float(row["frame_number"])),
                "timestamp_ms": float(row["timestamp_ms"]),
            })

    return sorted(round_starts, key=lambda item: item["timestamp_ms"])


def build_phase_segments(round_starts, buy_phase_sec=15.0):
    segments = []
    buy_phase_ms = buy_phase_sec * 1000

    for index, start in enumerate(round_starts):
        round_number = index + 1
        next_start = round_starts[index + 1] if index + 1 < len(round_starts) else None
        round_end_ms = next_start["timestamp_ms"] if next_start else math.inf

        buy_end_ms = min(start["timestamp_ms"] + buy_phase_ms, round_end_ms)

        segments.append({
            "round_number": round_number,
            "phase": "buy_phase",
            "start_ms": start["timestamp_ms"],
            "end_ms": buy_end_ms,
            "start_frame": start["frame_number"],
            "enemy_detection_enabled": False,
        })

        if buy_end_ms < round_end_ms:
            segments.append({
                "round_number": round_number,
                "phase": "live",
                "start_ms": buy_end_ms,
                "end_ms": round_end_ms,
                "start_frame": None,
                "enemy_detection_enabled": True,
            })

    return segments


def segment_for_timestamp(segments, timestamp_ms):
    for segment in segments:
        if segment["start_ms"] <= timestamp_ms < segment["end_ms"]:
            return segment
    return None


def phase_for_frame(segments, timestamp_ms):
    if not segments:
        return {
            "round_number": None,
            "phase": "unsegmented",
            "enemy_detection_enabled": True,
            "gate_reason": "no_round_segments",
        }

    segment = segment_for_timestamp(segments, timestamp_ms)
    if segment is None:
        return {
            "round_number": None,
            "phase": "outside_round",
            "enemy_detection_enabled": False,
            "gate_reason": "outside_known_round_segments",
        }

    phase = segment["phase"]
    return {
        "round_number": segment["round_number"],
        "phase": phase,
        "enemy_detection_enabled": segment["enemy_detection_enabled"],
        "gate_reason": "phase_allows_detection" if segment["enemy_detection_enabled"] else f"phase_{phase}",
    }


def serialize_segments(segments):
    serialized = []
    for segment in segments:
        end_ms = None if math.isinf(segment["end_ms"]) else segment["end_ms"]
        serialized.append({
            **segment,
            "end_ms": end_ms,
        })
    return serialized
