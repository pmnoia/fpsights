import json
import os


def write_json(data, output_path):
    """
    Write the full pipeline output dict to a JSON file.

    Output contract:
        {
            "run":     { video metadata + extraction settings },
            "round_segments": [ inferred round/phase windows ],
            "frames":  [ per-frame detection dicts ],
            "events":  [ phase_change / enemy_visible / enemy_lost transitions ],
            "summary": { frame counts + event count }
        }
    """
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"JSON written to: {output_path}")
