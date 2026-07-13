def build_events(detections):
    # Detect phase changes plus enemy_visible / enemy_lost transitions between frames.
    events = []
    prev_had_enemy = False
    prev_phase_key = None

    for det in detections:
        phase_key = (det.get("round_number"), det.get("phase"))
        if phase_key != prev_phase_key:
            events.append({
                "type": "phase_change",
                "round_number": det.get("round_number"),
                "phase": det.get("phase"),
                "frame_number": det["frame_number"],
                "timestamp_ms": det["timestamp_ms"],
            })
            prev_phase_key = phase_key

        has_enemy = len(det["enemy_positions"]) > 0

        if has_enemy and not prev_had_enemy:
            events.append({
                "type": "enemy_visible",
                "round_number": det.get("round_number"),
                "phase": det.get("phase"),
                "frame_number": det["frame_number"],
                "timestamp_ms": det["timestamp_ms"],
            })
        elif not has_enemy and prev_had_enemy:
            events.append({
                "type": "enemy_lost",
                "round_number": det.get("round_number"),
                "phase": det.get("phase"),
                "frame_number": det["frame_number"],
                "timestamp_ms": det["timestamp_ms"],
            })

        prev_had_enemy = has_enemy

    return events
