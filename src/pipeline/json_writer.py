import json
from pathlib import Path

def save_json(data, output_path):
    output_file = Path(output_path)

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)