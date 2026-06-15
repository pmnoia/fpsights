# FPSights
## Desktop FPS VOD Analysis & Coaching Assistant

FPSights is a desktop application that analyzes recorded FPS gameplay videos (VODs) and generates automated post-match coaching reports. It uses computer vision to measure crosshair placement, reaction time, and player positioning, then provides actionable insights for improvement.

### Features (MVP)
- Crosshair placement tracking and alignment scoring
- Reaction time estimation from enemy encounters
- Player positioning heatmap with kill/death markers
- Automated post-match report (in-app + PDF export)

### Tech Stack
- **Language:** Python 3.11+
- **Desktop UI:** PySide6
- **Computer Vision:** OpenCV (+ optional YOLO)
- **Database:** SQLite
- **Reporting:** Matplotlib + ReportLab / HTML-to-PDF

### Project Structure
```
fpsights/
├── src/
│   ├── pipeline/     # CV processing: frame extraction, detection, metrics
│   ├── ui/           # PySide6 desktop interface
│   ├── db/           # SQLite database layer
│   └── utils/        # Helpers, config, constants
├── docs/             # Project documentation
├── annotations/      # Ground-truth labeling guide + benchmark data
├── maps/             # Game map images for heatmap overlays
├── data/             # Sample VODs (gitignored) + output
└── tests/            # Unit and integration tests
```

### Getting Started
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Team
- [Name] — Project Lead + CV Pipeline
- [Name] — Desktop UI + Dashboard
- [Name] — Database + Integration
- [Name] — Testing + Documentation

