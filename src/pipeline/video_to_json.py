import argparse
from detector import detect, get_crosshair
from event_builder import build_events
from frame_reader import get_video_info, read_frames
from json_writer import write_json
from phase_segmenter import build_phase_segments, load_round_starts, phase_for_frame, serialize_segments


def parse_args():
    parser = argparse.ArgumentParser(description="Run FPSights detection on a VOD and write JSON output.")
    parser.add_argument("--input",           required=True)
    parser.add_argument("--output",          required=True)
    parser.add_argument("--frame-skip",      type=int, default=1)
    parser.add_argument("--max-frames",      type=int,   default=None)
    parser.add_argument("--start-time",      type=float, default=0, help="Start time in seconds")
    parser.add_argument("--method",          default="color", choices=["motion", "color"])
    parser.add_argument("--highlight-color", default="purple", choices=["red", "yellow", "purple"])
    parser.add_argument("--rounds-csv",      default=None, help="Optional annotations CSV with round_start rows")
    parser.add_argument("--buy-phase-sec",   type=float, default=0.0)
    args = parser.parse_args()

    if args.frame_skip < 1:
        parser.error("--frame-skip must be 1 or greater")
    if args.max_frames is not None and args.max_frames < 1:
        parser.error("--max-frames must be 1 or greater")
    if args.start_time < 0:
        parser.error("--start-time cannot be negative")
    if args.buy_phase_sec < 0:
        parser.error("--buy-phase-sec cannot be negative")

    return args


def skipped_detection(frame, frame_number, timestamp_ms, method, phase_info):
    height, width = frame.shape[:2]
    crosshair_x, crosshair_y = get_crosshair(width, height)

    return {
        "frame_number": frame_number,
        "timestamp_ms": timestamp_ms,
        "crosshair_x": crosshair_x,
        "crosshair_y": crosshair_y,
        "enemy_positions": [],
        "round_number": phase_info["round_number"],
        "phase": phase_info["phase"],
        "enemy_detection_enabled": False,
        "phase_meta": {"gate_reason": phase_info["gate_reason"]},
        "detector_meta": {
            "method": method,
            "crosshair_confidence": 1.0,
            "detection_skipped": True,
            "skip_reason": phase_info["gate_reason"],
        },
    }


def attach_phase(result, phase_info):
    result["round_number"] = phase_info["round_number"]
    result["phase"] = phase_info["phase"]
    result["enemy_detection_enabled"] = phase_info["enemy_detection_enabled"]
    result["phase_meta"] = {"gate_reason": phase_info["gate_reason"]}
    result["detector_meta"]["detection_skipped"] = False
    return result


def process_video(
    input_path,
    output_json,
    frame_skip,
    max_frames,
    method,
    highlight_color,
    start_time=0,
    rounds_csv=None,
    buy_phase_sec=0.0,
):
    fps, width, height, total_frames = get_video_info(input_path)
    round_starts = load_round_starts(rounds_csv)
    phase_segments = build_phase_segments(round_starts, buy_phase_sec)

    print(f"Video: {input_path}\nResolution: {width}x{height} \nFPS: {fps:.1f}fps")
    print(f"Method: {method} / {highlight_color}  skip={frame_skip}  max={max_frames}  start={start_time}s")
    if rounds_csv:
        print(f"Round gating: {rounds_csv}  rounds={len(round_starts)}  buy_phase={buy_phase_sec}s")
    else:
        print("Round gating: disabled (no --rounds-csv provided)")

    detections = []
    prev_frame = None

    for i, (frame, frame_num, ts_ms) in enumerate(read_frames(input_path, frame_skip, max_frames, start_time=start_time)):
        phase_info = phase_for_frame(phase_segments, ts_ms)

        if phase_info["enemy_detection_enabled"]:
            result = detect(frame, frame_num, ts_ms, prev_frame, method, highlight_color)
            result = attach_phase(result, phase_info)
        else:
            result = skipped_detection(frame, frame_num, ts_ms, method, phase_info)

        detections.append(result)
        prev_frame = frame
        skipped = " skipped" if result["detector_meta"]["detection_skipped"] else ""
        print(
            f"  [{i+1}] frame={frame_num}  t={ts_ms}ms  "
            f"round={result['round_number']} phase={result['phase']}{skipped}  "
            f"enemies={len(result['enemy_positions'])}"
        )

    events = build_events(detections)
    frames_with_enemies = sum(1 for d in detections if d["enemy_positions"])
    frames_detection_skipped = sum(1 for d in detections if d["detector_meta"].get("detection_skipped"))

    output = {
        "run": {
            "input_path":     input_path,
            "width":          width,
            "height":         height,
            "fps":            round(fps, 4),
            "total_frames":   total_frames,
            "duration_sec":   round(total_frames / fps, 4) if fps > 0 else 0,
            "frame_skip":     frame_skip,
            "max_frames":     max_frames,
            "method":         method,
            "highlight_color": highlight_color,
            "rounds_csv":     rounds_csv,
            "buy_phase_sec":  buy_phase_sec,
        },
        "round_segments": serialize_segments(phase_segments),
        "frames":  detections,
        "events":  events,
        "summary": {
            "frames_processed":    len(detections),
            "frames_with_enemies": frames_with_enemies,
            "frames_detection_skipped": frames_detection_skipped,
            "total_events":        len(events),
        },
    }

    write_json(output, output_json)
    print(f"Done. {len(detections)} frames, {len(events)} events -> {output_json}")


def main():
    print("--------Valorant Video Processing Tool---------")
    args = parse_args()
    process_video(
        args.input,
        args.output,
        args.frame_skip,
        args.max_frames,
        args.method,
        args.highlight_color,
        args.start_time,
        args.rounds_csv,
        args.buy_phase_sec,
    )


if __name__ == "__main__":
    main()
