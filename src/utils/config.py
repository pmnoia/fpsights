"""FPSights project configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
ANNOTATIONS_DIR = PROJECT_ROOT / "annotations"
MAPS_DIR = PROJECT_ROOT / "maps"
DB_PATH = DATA_DIR / "fpsights.db"

WINDOW_TITLE = "FPSights — FPS VOD Analysis"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# Video defaults
DEFAULT_INPUT_MINUTES_MIN = 20
DEFAULT_INPUT_MINUTES_MAX = 45
DEFAULT_FPS = 60
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080

# Frame extraction tuning
FRAME_SKIP = 3
USE_FRAME_SKIP = True

# Detection thresholds (initial values; tune in Week 10)
NEAR_TARGET_RADIUS_PX = 50
CROSSHAIR_CONFIDENCE_MIN = 0.60
ENEMY_MIN_AREA = 500


def ensure_dirs() -> None:
    """Create required runtime directories."""
    for p in (DATA_DIR, OUTPUT_DIR, ANNOTATIONS_DIR):
        p.mkdir(parents=True, exist_ok=True)

