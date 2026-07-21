# FPSights — Scope Document

## Project Identity

- **App Name:** FPSights
- **Tagline:** Desktop FPS VOD Analysis & Coaching Assistant
- **Type:** Desktop application (Python + PySide6)
- **Target Users:** FPS players (casual to competitive) seeking objective performance feedback

## Core Problem

Players improve through subjective replay review. They lack objective, repeatable metrics to measure crosshair placement, reaction time, and positioning quality.

## MVP Features (Must Deliver)

1. **Crosshair Placement Tracking** — Detect crosshair center per frame; score alignment quality
2. **Reaction Time Estimation** — Measure time from enemy appearance to first correction/shot
3. **Player Positioning Heatmap** — Track movement from minimap; overlay kill/death markers on map
4. **Automated Post-Match Report** — KPI summary, strengths/weaknesses, coaching recommendations (in-app + PDF export)

## Out of Scope (Future)

- Real-time live match analysis
- Multi-game support (start with one FPS title)
- Cloud/web deployment
- User accounts / multi-player comparison
- Color/HSV thresholding for enemy detection

## Technical Constraints

- Platform: Desktop only (macOS first, cross-platform later)
- Language: Python 3.11+
- UI Framework: PySide6
- CV: YOLO for enemy detection; OpenCV for video I/O and frame processing
- Database: SQLite (local)
- Video Input: .mp4 / .mkv, 20–45 minutes
- Processing: Offline, single-machine, async worker thread

## Success Criteria (Evaluation Metrics)

| Metric                             | Target                  |
| ---------------------------------- | ----------------------- |
| Enemy detection precision          | ≥ 0.70                  |
| Enemy detection recall             | ≥ 0.65                  |
| Crosshair localization error       | ≤ 10 px                 |
| Reaction-time MAE vs manual labels | ≤ 100 ms                |
| Processing time (20-min VOD)       | ≤ 20 min                |
| End-to-end system reliability      | No crash on 5 full VODs |

## Team Roles

| Role                       | Primary Owner              |
| -------------------------- | -------------------------- |
| Project Lead + CV Pipeline | Phone Maung + Nyi Min Htet |
| Desktop UI + Dashboard     | Nyi Min Htet               |
| Database + Integration     | Phone Maung                |
| Testing + Documentation    | Kyaw Zeyar Hein            |

## Timeline

- Month 1 (Weeks 1–4): Foundation & Prototype
- Month 2 (Weeks 5–8): Core Analytics Engine
- Month 3 (Weeks 9–12): Reporting, Validation & Finalization
