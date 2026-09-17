from __future__ import annotations

from src.history import list_analyses, save_analysis


def test_saves_and_lists_completed_analysis(tmp_path) -> None:
    database = tmp_path / "fpsights.sqlite"
    result = {
        "video": {"path": "/videos/example.mp4"},
        "artifacts": {"metrics": "/output/example/metrics.json"},
        "analytics": {
            "crosshair": {"score_percent": 49.1},
            "aim_reaction": {"average_ms": 100, "encounters": 3},
            "positioning": {"coverage_percent": 96.5},
        },
        "detection": {"total_detections": 12},
        "segmentation": {"rounds": 2},
    }

    save_analysis(database, result)
    rows = list_analyses(database)

    assert len(rows) == 1
    assert rows[0]["video_path"] == "/videos/example.mp4"
    assert rows[0]["crosshair_score"] == 49.1
    assert rows[0]["minimap_coverage"] == 96.5
