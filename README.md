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
