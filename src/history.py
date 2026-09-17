"""Local SQLite persistence for completed FPSights analyses."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyzed_at TEXT NOT NULL,
    video_path TEXT NOT NULL,
    run_path TEXT NOT NULL UNIQUE,
    crosshair_score REAL,
    aim_ms REAL,
    encounters INTEGER NOT NULL,
    minimap_coverage REAL,
    detections INTEGER NOT NULL,
    rounds INTEGER NOT NULL
)
"""


def initialize_history(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(SCHEMA)


def save_analysis(database_path: Path, result: dict[str, Any]) -> None:
    initialize_history(database_path)
    analytics = result.get("analytics") or {}
    crosshair = analytics.get("crosshair") or {}
    aim = analytics.get("aim_reaction") or {}
    positioning = analytics.get("positioning") or {}
    detection = result.get("detection") or {}
    segmentation = result.get("segmentation") or {}
    artifacts = result.get("artifacts") or {}
    video = result.get("video") or {}

    run_path = str(Path(str(artifacts.get("metrics", "unknown"))).parent)
    values = (
        datetime.now().isoformat(timespec="seconds"),
        str(video.get("path", "Unknown video")),
        run_path,
        _number_or_none(crosshair.get("score_percent")),
        _number_or_none(aim.get("average_ms")),
        int(aim.get("encounters", 0)),
        _number_or_none(positioning.get("coverage_percent")),
        int(detection.get("total_detections", 0)),
        int(segmentation.get("rounds", 0)),
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO matches (
                analyzed_at, video_path, run_path, crosshair_score, aim_ms,
                encounters, minimap_coverage, detections, rounds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_path) DO UPDATE SET
                analyzed_at=excluded.analyzed_at,
                video_path=excluded.video_path,
                crosshair_score=excluded.crosshair_score,
                aim_ms=excluded.aim_ms,
                encounters=excluded.encounters,
                minimap_coverage=excluded.minimap_coverage,
                detections=excluded.detections,
                rounds=excluded.rounds
            """,
            values,
        )


def list_analyses(database_path: Path, limit: int = 50) -> list[dict[str, Any]]:
    initialize_history(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM matches ORDER BY analyzed_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _number_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
