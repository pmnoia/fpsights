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

## Repository Structure
```text
fpsights/
├── UI/FPSights_Pro_UI/        
│   └── fpsights_pro_ui.py
├── src/                       
│   ├── main.py
│   └── utils/config.py
├── docs/
├── annotations/
├── maps/
├── requirements.txt
└── README.md
```

## Project Setup
Run these commands from the `fpsights` folder.

```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Launch UI Prototype
```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
source venv/bin/activate
python UI/FPSights_Pro_UI/fpsights_pro_ui.py
```

## Launch Current App Entry (non-UI stub)
```bash
cd /Users/phonemaung/au/2026-1/csx3010/fpsights
source venv/bin/activate
python src/main.py
```

## Annotation Assets
- Schema guide: `annotations/ANNOTATION_GUIDE.md`
- Sample labels: `annotations/vod_001_sample.csv`

## Common Issues
- **`ModuleNotFoundError: PySide6`**  
  Make sure venv is activated and reinstall dependencies:
  `pip install -r requirements.txt`
- **UI does not open on macOS**  
  Run the script directly (not from a restricted environment), and verify Python is from `venv/bin/python`.
