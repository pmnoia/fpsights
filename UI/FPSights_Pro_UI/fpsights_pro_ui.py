"""

FPSights Pro Gaming UI

"""

import sys
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QObject, QRect, QThread, QUrl, Signal, Slot

from PySide6.QtGui import (
    QDesktopServices, QFont, QPainter, QColor, QPen, QBrush, QLinearGradient,
    QPixmap,
)

from PySide6.QtWidgets import (

    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,

    QHBoxLayout, QGridLayout, QStackedWidget, QFileDialog, QProgressBar, QTableWidget,

    QTableWidgetItem, QSizePolicy, QScrollArea, QComboBox, QLineEdit, QMessageBox

)

# ------------------------------------------------------------
# FPSights backend connection
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.processor import ProcessingConfig, process_video
from src.reporting import coaching_recommendations, generate_pdf_report
from src.history import initialize_history, list_analyses, save_analysis


BG = "#070d14"

PANEL = "#0d1722"

PANEL2 = "#111e2c"

BORDER = "#22384e"

TEXT = "#f4f7fb"

MUTED = "#9fb3c8"

RED = "#ff375f"

GREEN = "#20e080"

YELLOW = "#ffd166"

STYLE = f"""

QMainWindow {{ background: {BG}; }}

QWidget {{ color: {TEXT}; font-family: Arial; font-size: 14px; }}

QFrame#Sidebar {{ background: #08111b; border-right: 1px solid {BORDER}; }}

QFrame#Card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}

QFrame#CardHot {{ background: #120d16; border: 1px solid {RED}; border-radius: 10px; }}

QPushButton {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 10px 14px; font-weight: bold; }}

QPushButton:hover {{ border: 1px solid {RED}; background: #172538; }}

QPushButton#ActiveNav {{ background: #3b1220; color: {RED}; border-left: 4px solid {RED}; border-radius: 7px; text-align: left; }}

QPushButton#Nav {{ text-align: left; border: none; background: transparent; padding-left: 18px; }}

QPushButton#Nav:hover {{ background: #111e2c; color: {RED}; }}

QPushButton#Primary {{ background: {RED}; color: white; border: none; }}

QPushButton#Primary:hover {{ background: #ff5575; }}

QProgressBar {{ background: #0a111a; border: 1px solid {BORDER}; border-radius: 6px; height: 12px; text-align: center; }}

QProgressBar::chunk {{ background: {RED}; border-radius: 6px; }}

QTableWidget {{ background: #08111b; gridline-color: #1e3145; border: 1px solid {BORDER}; border-radius: 8px; }}

QHeaderView::section {{ background: {PANEL2}; color: {TEXT}; padding: 8px; border: none; font-weight: bold; }}

QLineEdit, QComboBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px; color: {TEXT}; }}

"""

class MiniChart(QFrame):

    def __init__(self, kind="radar"):

        super().__init__(); self.kind = kind; self.setMinimumHeight(190); self.setObjectName("Card")

    def paintEvent(self, e):

        super().paintEvent(e)

        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)

        w,h = self.width(), self.height(); cx,cy = w//2, h//2+12

        p.setPen(QPen(QColor("#46617c"),1))

        for r in [35,60,85]:

            pts=[]

            for i in range(5):

                import math

                a = -math.pi/2 + i*2*math.pi/5

                pts.append((cx+int(math.cos(a)*r), cy+int(math.sin(a)*r)))

            for i in range(5): p.drawLine(*pts[i], *pts[(i+1)%5])

        p.setPen(QPen(QColor(RED),3)); p.setBrush(QColor(255,55,95,70))

        vals=[70,82,75,45,68]; pts=[]

        import math

        for i,v in enumerate(vals):

            r=v/100*85; a=-math.pi/2+i*2*math.pi/5

            pts.append((cx+int(math.cos(a)*r), cy+int(math.sin(a)*r)))

        from PySide6.QtGui import QPolygon

        from PySide6.QtCore import QPoint

        p.drawPolygon(QPolygon([QPoint(x,y) for x,y in pts]))

        p.setPen(QColor(TEXT)); p.setFont(QFont("Arial",9, QFont.Bold)); p.drawText(16,28,"ANALYSIS SUMMARY")

class VideoMock(QFrame):

    def __init__(self):

        super().__init__(); self.setMinimumHeight(330); self.setObjectName("Card")

    def paintEvent(self,e):

        super().paintEvent(e); p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)

        w,h=self.width(),self.height()

        grad=QLinearGradient(0,0,w,h); grad.setColorAt(0,QColor("#1a0f13")); grad.setColorAt(1,QColor("#07101a")); p.fillRect(12,12,w-24,h-24,grad)

        p.setPen(QPen(QColor("#5f6670"),2))

        for x in range(80,w-40,110): p.drawLine(x,60,x+40,h-90)

        for y in range(75,h-110,55): p.drawLine(55,y,w-65,y-10)

        p.setPen(QPen(QColor(RED),3)); p.setBrush(QColor(255,55,95,35))

        p.drawRect(w//2+20,h//2-40,64,90); p.drawRect(w//2+175,h//2-35,60,85)

        p.drawLine(w//2+52,h//2-10,w//2+52,h//2+25); p.drawLine(w//2+38,h//2+5,w//2+66,h//2+5)

        p.setPen(QPen(QColor("#e8edf5"),2)); p.setFont(QFont("Arial",12,QFont.Bold)); p.drawText(w//2-40,42,"8      1:12      6")

        p.setPen(QPen(QColor(RED),5)); p.drawLine(45,h-64,w//2-20,h-64); p.setPen(QPen(QColor("#7d8794"),4)); p.drawLine(w//2-20,h-64,w-50,h-64)

        p.setPen(QColor(TEXT)); p.setFont(QFont("Arial",11,QFont.Bold)); p.drawText(45,h-35,"▶  ▌▌     00:12 / 25:43                                      1.0x  ⚙  ⛶")

class HeatmapMock(QFrame):

    def __init__(self):
        super().__init__(); self.setMinimumHeight(230); self.setObjectName("Card")
        self.heatmap_pixmap = None

    def set_image(self, image_path):
        pixmap = QPixmap(str(image_path))
        self.heatmap_pixmap = pixmap if not pixmap.isNull() else None
        self.update()

    def paintEvent(self,e):

        super().paintEvent(e); p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)

        if self.heatmap_pixmap is not None:
            target = QRect(14, 14, self.width()-28, self.height()-28)
            scaled = self.heatmap_pixmap.scaled(
                target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = target.x() + (target.width() - scaled.width()) // 2
            y = target.y() + (target.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            return

        p.setPen(QColor(MUTED)); p.setFont(QFont("Arial",12,QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, "Run an analysis to generate a heatmap")

class StatCard(QFrame):
    def __init__(self, title, value, sub, icon="◇"):
        super().__init__()
        self.setObjectName("Card")
        self.setMinimumHeight(100)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)

        ic = QLabel(icon)
        ic.setStyleSheet(f"color:{RED}; font-size:28px;")
        lay.addWidget(ic)

        box = QVBoxLayout()

        self.title_label = label(title, 10, MUTED, True)
        self.value_label = label(value, 24, TEXT, True)
        self.sub_label = label(sub, 11, GREEN, True)

        box.addWidget(self.title_label)
        box.addWidget(self.value_label)
        box.addWidget(self.sub_label)

        lay.addLayout(box)
        lay.addStretch()

    def set_value(self, value, sub=""):
        self.value_label.setText(str(value))
        self.sub_label.setText(str(sub))


def label(text, size=12, color=TEXT, bold=False):

    l=QLabel(text); l.setStyleSheet(f"color:{color}; font-size:{size}px;" + ("font-weight:bold;" if bold else "")); l.setWordWrap(True); return l

def card_title(t): return label(t,13,TEXT,True)

def _display_metric(value, suffix):
    return f"{value:.1f}{suffix}" if isinstance(value, (int, float)) else "N/A"


class AnalysisWorker(QObject):
    """Run the existing FPSights processor without freezing the PySide6 UI."""

    progress = Signal(int, int)
    succeeded = Signal(dict)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config

    @Slot()
    def run(self):
        try:
            result = process_video(
                self.config,
                progress=lambda done, total: self.progress.emit(done, total),
            )
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class FPSightsPro(QMainWindow):

    def __init__(self):

        super().__init__()
        self.selected_video = None
        self.analysis_thread = None
        self.analysis_worker = None
        self.last_analysis_result = None
        self.coach_feedback_labels = []
        self.history_path = PROJECT_ROOT / "output" / "fpsights-history.sqlite"
        initialize_history(self.history_path)

        self.setWindowTitle("FPSights Pro Gaming UI"); self.resize(1440, 920); self.setMinimumSize(1100,720); self.setStyleSheet(STYLE)

        root=QWidget(); self.setCentralWidget(root); main=QHBoxLayout(root); main.setContentsMargins(0,0,0,0); main.setSpacing(0)

        self.sidebar=QFrame(); self.sidebar.setObjectName("Sidebar"); self.sidebar.setFixedWidth(245); main.addWidget(self.sidebar)

        self.build_sidebar()

        self.stack=QStackedWidget(); main.addWidget(self.stack,1)

        self.pages=[]

        self.add_page("Dashboard", self.dashboard_page())

        self.add_page("Analyze VOD", self.analyze_page())

        self.add_page("Report", self.report_page())

        self.add_page("Heatmap", self.heatmap_page())

        self.add_page("History", self.compare_page())

        self.add_page("Settings", self.settings_page())

        self.set_active(1)
        self.refresh_dashboard()

    def build_sidebar(self):

        lay=QVBoxLayout(self.sidebar); lay.setContentsMargins(22,26,0,22); lay.setSpacing(14)

        lay.addWidget(label("◢  FPSights",26,TEXT,True)); lay.addWidget(label("     AI Gameplay Coach",13,MUTED)); lay.addSpacing(30)

        self.nav=[]

        for name, icon in [("Dashboard","⌂"),("Analyze VOD","▣"),("Report","▤"),("Heatmap","◎"),("History","⇄"),("Settings","⚙")]:

            b=QPushButton(f"{icon}  {name.upper()}"); b.setObjectName("Nav"); b.setFixedHeight(46); b.clicked.connect(lambda _,i=len(self.nav): self.set_active(i)); lay.addWidget(b); self.nav.append(b)

        lay.addStretch(); status=QFrame(); status.setObjectName("Card"); status.setFixedHeight(125); r=QVBoxLayout(status); r.addWidget(label("LOCAL MVP",11,MUTED,True)); r.addWidget(label("Offline Analysis",18,TEXT,True)); r.addWidget(label("YOLO11n • SQLite",12,MUTED)); lay.addWidget(status)

    def add_page(self, name, widget): self.pages.append(name); self.stack.addWidget(widget)

    def set_active(self, idx):

        self.stack.setCurrentIndex(idx)

        for i,b in enumerate(self.nav): b.setObjectName("ActiveNav" if i==idx else "Nav"); b.style().unpolish(b); b.style().polish(b)

    def wrap(self, content):

        area=QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QFrame.NoFrame); area.setWidget(content); return area

    def header(self, title, export_callback=None):

        row=QHBoxLayout(); left=QVBoxLayout(); left.addWidget(label(title,24,TEXT,True)); left.addWidget(label("Local offline Valorant VOD analysis",13,MUTED)); row.addLayout(left); row.addStretch()

        if export_callback is not None:
            ex=QPushButton("↓  Export Report"); ex.setObjectName("Primary")
            ex.clicked.connect(export_callback)
            row.addWidget(ex)
        return row

    def dashboard_page(self):

        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Dashboard"))

        self.dashboard_latest_label = label("No completed analysis yet.",14,MUTED)
        lay.addWidget(self.dashboard_latest_label)

        grid=QGridLayout(); grid.setSpacing(12)
        self.dashboard_aim = StatCard("AIM ACQUISITION","N/A","Latest saved analysis","⚡")
        self.dashboard_crosshair = StatCard("CROSSHAIR SCORE","N/A","Latest saved analysis","⌖")
        self.dashboard_minimap = StatCard("MINIMAP TRACKING","N/A","Latest saved analysis","🛡")
        self.dashboard_detections = StatCard("DETECTIONS","N/A","Latest saved analysis","◎")
        self.dashboard_rounds = StatCard("ROUNDS","N/A","Latest saved analysis","◇")

        for i, card in enumerate([
            self.dashboard_aim,
            self.dashboard_crosshair,
            self.dashboard_minimap,
            self.dashboard_detections,
            self.dashboard_rounds,
        ]):
            grid.addWidget(card,0,i)

        note=QFrame(); note.setObjectName("Card"); note_layout=QVBoxLayout(note)
        note_layout.addWidget(card_title("LATEST ANALYSIS"))
        note_layout.addWidget(label("Use Analyze VOD to create a new result. Review detections, heatmap, coaching feedback, and PDF from the navigation menu.",13,MUTED))

        lay.addLayout(grid); lay.addWidget(note); lay.addStretch(); return self.wrap(w)

    def analyze_page(self):
        w=QWidget()
        lay=QVBoxLayout(w)
        lay.setContentsMargins(26,24,26,24)

        # Keep the existing FPSights visual design, but connect the controls.
        top=QHBoxLayout()
        title_box=QVBoxLayout()
        title_box.addWidget(label("Analyze VOD",24,TEXT,True))

        self.selected_video_label = label("No VOD selected",13,MUTED)
        title_box.addWidget(self.selected_video_label)

        top.addLayout(title_box)
        top.addStretch()

        self.choose_vod_button = QPushButton("Upload VOD")
        self.choose_vod_button.clicked.connect(self.choose_video)

        self.start_analysis_button = QPushButton("Analyze")
        self.start_analysis_button.setObjectName("Primary")
        self.start_analysis_button.setEnabled(False)
        self.start_analysis_button.clicked.connect(self.start_analysis)

        self.open_review_button = QPushButton("Open Review Video")
        self.open_review_button.setEnabled(False)
        self.open_review_button.clicked.connect(self.open_review_video)

        top.addWidget(self.choose_vod_button)
        top.addWidget(self.start_analysis_button)
        top.addWidget(self.open_review_button)
        lay.addLayout(top)

        # Analysis status/progress.
        status_card=QFrame()
        status_card.setObjectName("Card")
        status_layout=QVBoxLayout(status_card)

        self.analysis_status_label = label(
            "Choose a gameplay video to begin.",
            12,
            MUTED,
        )

        self.analysis_progress = QProgressBar()
        self.analysis_progress.setRange(0,100)
        self.analysis_progress.setValue(0)

        status_layout.addWidget(self.analysis_status_label)
        status_layout.addWidget(self.analysis_progress)
        lay.addWidget(status_card)

        # Same card-based UI, now with references that can receive backend results.
        grid=QGridLayout()
        grid.setSpacing(12)

        self.aim_card = StatCard("AIM ACQUISITION","N/A","Waiting for analysis","⚡")
        self.crosshair_card = StatCard("CROSSHAIR SCORE","N/A","Waiting for analysis","⌖")
        self.positioning_card = StatCard("MINIMAP TRACKING","N/A","Waiting for analysis","🛡")
        for i, card in enumerate([
            self.aim_card,
            self.crosshair_card,
            self.positioning_card,
        ]):
            grid.addWidget(card,0,i)

        lay.addLayout(grid)
        lay.addWidget(self.coach_card())

        bottom=QHBoxLayout()

        self.analysis_event_table = QTableWidget(0,5)
        self.analysis_event_table.setHorizontalHeaderLabels(
            ["#","TIME","EVENT","ROUND","DETAILS"]
        )
        self.analysis_event_table.verticalHeader().setVisible(False)
        self.analysis_event_table.setMinimumHeight(230)
        self.analysis_event_table.horizontalHeader().setStretchLastSection(True)

        bottom.addWidget(self.analysis_event_table,3)
        self.analysis_heatmap = HeatmapMock()
        bottom.addWidget(self.analysis_heatmap,2)
        lay.addLayout(bottom)

        return self.wrap(w)

    def choose_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose FPS Gameplay VOD",
            "",
            "Videos (*.mp4 *.mkv *.mov)",
        )

        if not file_path:
            return

        self.selected_video = Path(file_path)

        if hasattr(self, "selected_video_label"):
            self.selected_video_label.setText(self.selected_video.name)

        if hasattr(self, "analysis_status_label"):
            self.analysis_status_label.setText(
                "VOD selected. Click Analyze to start processing."
            )

        if hasattr(self, "analysis_progress"):
            self.analysis_progress.setRange(0,100)
            self.analysis_progress.setValue(0)

        if hasattr(self, "start_analysis_button"):
            self.start_analysis_button.setEnabled(True)

        if hasattr(self, "open_review_button"):
            self.open_review_button.setEnabled(False)

    def find_model_path(self):
        """Find the team's development YOLO model if it exists."""
        # preferred = (
        #     PROJECT_ROOT
        #     / "runs"
        #     / "detect"
        #     / "vod01-yolo11n"
        #     / "weights"
        #     / "best.pt"
        # )

        # if preferred.exists():
        #     return preferred

        # detect_dir = PROJECT_ROOT / "runs" / "detect"

        # if detect_dir.exists():
        #     candidates = list(detect_dir.glob("*/weights/best.pt"))
        #     if candidates:
        #         return sorted(candidates)[-1]

        # return None
        model = PROJECT_ROOT / "models" / "fpsights-yolo11n-960.pt"
        return model if model.exists() else None

    def start_analysis(self):
        if self.selected_video is None:
            QMessageBox.warning(
                self,
                "No VOD Selected",
                "Please choose a gameplay video first.",
            )
            return

        if not self.selected_video.exists():
            QMessageBox.critical(
                self,
                "Video Missing",
                "The selected video file no longer exists.",
            )
            return

        if self.analysis_thread is not None:
            QMessageBox.information(
                self,
                "Analysis Running",
                "FPSights is already analyzing a video.",
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (
            PROJECT_ROOT
            / "output"
            / self.selected_video.stem
            / timestamp
        )

        model_path = self.find_model_path()

        config = ProcessingConfig(
            video_path=self.selected_video,
            output_dir=output_dir,
            model_path=model_path,
            confidence=0.25,
            frame_skip=5,
            sample_rate=2.0,
            device="cpu" if model_path is not None else None,
            preview=False,
            review_video=model_path is not None,
        )

        self.choose_vod_button.setEnabled(False)
        self.start_analysis_button.setEnabled(False)
        self.open_review_button.setEnabled(False)

        # Segmentation runs before the detector progress callback,
        # so use an indeterminate bar until frame processing begins.
        self.analysis_progress.setRange(0,0)

        if model_path is None:
            self.analysis_status_label.setText(
                "Running segmentation... YOLO model not found, so detection metrics will be unavailable."
            )
        else:
            self.analysis_status_label.setText(
                "Running segmentation and preparing enemy detection..."
            )

        self.analysis_thread = QThread()
        self.analysis_worker = AnalysisWorker(config)

        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(self.update_analysis_progress)
        self.analysis_worker.succeeded.connect(self.analysis_succeeded)
        self.analysis_worker.failed.connect(self.analysis_failed)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)

        self.analysis_thread.finished.connect(self.analysis_finished)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)

        self.analysis_thread.start()

    @Slot(int, int)
    def update_analysis_progress(self, done, total):
        self.analysis_progress.setRange(0,100)

        percent = round(done / total * 100) if total else 0
        percent = max(0, min(100, percent))

        self.analysis_progress.setValue(percent)
        self.analysis_status_label.setText(
            f"Detecting enemies and computing metrics... {percent}%"
        )

    @Slot(dict)
    def analysis_succeeded(self, result):
        self.last_analysis_result = result

        self.analysis_progress.setRange(0,100)
        self.analysis_progress.setValue(100)

        analytics = result.get("analytics") or {}
        crosshair = analytics.get("crosshair") or {}
        aim = analytics.get("aim_reaction") or {}
        positioning = analytics.get("positioning") or {}

        crosshair_score = crosshair.get("score_percent")
        head_error = crosshair.get("mean_head_error_px")
        evaluated_frames = crosshair.get("evaluated_frames", 0)

        aim_ms = aim.get("average_ms")
        measured = aim.get("measured_encounters", 0)
        encounters = aim.get("encounters", 0)

        if crosshair_score is None:
            self.crosshair_card.set_value(
                "N/A",
                "No YOLO crosshair result",
            )
        else:
            sub = f"{evaluated_frames} frames • head error "
            sub += (
                f"{head_error:.1f}px"
                if isinstance(head_error, (int, float))
                else "N/A"
            )
            self.crosshair_card.set_value(
                f"{crosshair_score:.1f}%",
                sub,
            )

        if aim_ms is None:
            self.aim_card.set_value(
                "N/A",
                f"{measured}/{encounters} encounters measured",
            )
        else:
            self.aim_card.set_value(
                f"{aim_ms:.0f} ms",
                f"{measured}/{encounters} encounters measured",
            )

        positioning_samples = positioning.get("sample_count", 0)
        positioning_coverage = positioning.get("coverage_percent")
        if isinstance(positioning_coverage, (int, float)) and positioning_samples:
            self.positioning_card.set_value(
                f"{positioning_coverage:.1f}%",
                f"{positioning_samples} minimap samples",
            )
        else:
            self.positioning_card.set_value("N/A", "Player marker not detected")
        self.load_real_events(result)
        self.update_report_page(result)
        self.update_coaching_feedback(result)
        save_analysis(self.history_path, result)
        self.refresh_match_history()
        self.refresh_dashboard()

        heatmap_path = result.get("artifacts", {}).get("heatmap")
        if heatmap_path and Path(heatmap_path).exists():
            self.analysis_heatmap.set_image(heatmap_path)
            self.heatmap_view.set_image(heatmap_path)

        review_path = result.get("artifacts", {}).get("review_video")
        self.open_review_button.setEnabled(
            bool(review_path and Path(review_path).exists())
        )

        if analytics:
            self.analysis_status_label.setText("Analysis complete.")
        else:
            self.analysis_status_label.setText(
                "Segmentation complete. YOLO analytics were not generated."
            )

    def load_real_events(self, result):
        event_tables = [self.analysis_event_table, self.report_event_table]
        for table in event_tables:
            table.setRowCount(0)

        metrics_path = (
            result.get("artifacts", {})
            .get("metrics")
        )

        if not metrics_path:
            return

        path = Path(metrics_path)

        if not path.exists():
            return

        try:
            metrics = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        events = metrics.get("events", [])

        if not isinstance(events, list):
            return

        for table in event_tables:
            table.setRowCount(len(events))

        for row, event in enumerate(events):
            timestamp_ms = event.get("timestamp_ms", 0)
            event_type = event.get("type", "unknown")
            event_label = str(event_type).replace("_", " ").title()
            round_number = event.get("round_number")

            if isinstance(timestamp_ms, (int, float)):
                minutes = int(timestamp_ms) // 60000
                seconds = (int(timestamp_ms) % 60000) // 1000
                milliseconds = int(timestamp_ms) % 1000
                time_text = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            else:
                time_text = "00:00.000"

            detail = ""

            if event_type == "aim_acquired" and "reaction_ms" in event:
                reaction_ms = event["reaction_ms"]
                detail = (
                    "Already aligned"
                    if reaction_ms == 0
                    else f"{reaction_ms} ms"
                )

            values = [
                str(row + 1),
                time_text,
                event_label,
                str(round_number if round_number is not None else "—"),
                detail,
            ]

            for table in event_tables:
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(value))

    def update_coaching_feedback(self, result):
        analytics = result.get("analytics") or {}
        recommendations = coaching_recommendations(
            analytics.get("crosshair") or {},
            analytics.get("aim_reaction") or {},
        )

        for index, feedback_label in enumerate(self.coach_feedback_labels):
            if index < len(recommendations):
                feedback_label.setText(recommendations[index])
                feedback_label.show()
            else:
                feedback_label.hide()

    def open_review_video(self):
        if not self.last_analysis_result:
            return

        review_path = (
            self.last_analysis_result.get("artifacts", {})
            .get("review_video")
        )

        if not review_path or not Path(review_path).exists():
            QMessageBox.warning(
                self,
                "Review Video Missing",
                "No review video was produced for this analysis.",
            )
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(review_path)))

    def update_report_page(self, result):
        analytics = result.get("analytics") or {}
        crosshair = analytics.get("crosshair") or {}
        aim = analytics.get("aim_reaction") or {}

        score = crosshair.get("score_percent")
        reaction = aim.get("average_ms")
        measured = aim.get("measured_encounters", 0)
        encounters = aim.get("encounters", 0)

        self.report_crosshair_card.set_value(
            f"{score:.1f}%" if isinstance(score, (int, float)) else "N/A",
            "Crosshair placement score",
        )
        self.report_aim_card.set_value(
            f"{reaction:.1f} ms" if isinstance(reaction, (int, float)) else "N/A",
            f"{measured}/{encounters} encounters measured",
        )
        self.report_export_card.set_value("Ready", "PDF report available")

    def export_pdf_report(self):
        if not self.last_analysis_result:
            QMessageBox.information(
                self,
                "No Analysis",
                "Analyze a VOD before exporting a report.",
            )
            return

        metrics_path = self.last_analysis_result.get("artifacts", {}).get("metrics")
        default_directory = Path(metrics_path).parent if metrics_path else PROJECT_ROOT / "output"
        default_path = default_directory / "fpsights-report.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export FPSights Report",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return

        output_path = Path(file_path)
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        try:
            generate_pdf_report(self.last_analysis_result, output_path)
        except Exception as error:
            QMessageBox.critical(self, "Report Export Failed", str(error))
            return

        QMessageBox.information(
            self,
            "Report Exported",
            f"PDF report saved to:\n{output_path}",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path)))

    @Slot(str)
    def analysis_failed(self, error):
        self.analysis_progress.setRange(0,100)
        self.analysis_progress.setValue(0)
        self.analysis_status_label.setText(
            f"Analysis failed: {error}"
        )

        QMessageBox.critical(
            self,
            "FPSights Analysis Error",
            error,
        )

    @Slot()
    def analysis_finished(self):
        self.choose_vod_button.setEnabled(True)
        self.start_analysis_button.setEnabled(
            self.selected_video is not None
        )

        self.analysis_worker = None
        self.analysis_thread = None

    def event_timeline(self):

        c=QFrame(); c.setObjectName("Card"); c.setMinimumHeight(95); l=QVBoxLayout(c); l.addWidget(label("Event Markers   ◇ Enemy Visible    ⚠ Aim Correction    ✹ Shot Fired    ☠ Enemy Killed    💀 Player Died",12,TEXT))

        pb=QProgressBar(); pb.setValue(48); l.addWidget(pb); l.addWidget(label("00:00        05:00        10:00        15:00        20:00        25:43",11,MUTED)); return c

    def coach_card(self):

        c=QFrame(); c.setObjectName("CardHot"); c.setMinimumHeight(250); l=QVBoxLayout(c)

        l.addWidget(label("AI COACH FEEDBACK",13,RED,True));

        for placeholder in [
            "Analyze a VOD to generate coaching feedback.",
            "",
            "",
        ]:
            feedback_label = label(placeholder, 12, TEXT)
            self.coach_feedback_labels.append(feedback_label)
            l.addWidget(feedback_label)
        l.addStretch()

        b=QPushButton("View Full Report  ›"); b.setObjectName("Primary"); b.clicked.connect(lambda: self.set_active(2)); l.addWidget(b); return c

    def event_table(self):

        t=QTableWidget(6,6); t.setHorizontalHeaderLabels(["#","TIME","EVENT","DETAILS","REGION","VIDEO"]); t.verticalHeader().setVisible(False)

        rows=[("1","00:12.400","◇ Enemy Visible","1 enemy spotted","Mid","▶"),("2","00:12.610","⚠ Aim Correction","Moving crosshair","Mid","▶"),("3","00:12.920","✹ Shot Fired","First bullet fired","Mid","▶"),("4","00:13.100","☠ Enemy Killed","Kill confirmed","Mid","▶"),("5","00:25.800","◇ Enemy Visible","2 enemies spotted","A Site","▶"),("6","00:26.150","💀 Player Died","Killed by enemy","A Site","▶")]

        for r,row in enumerate(rows):

            for c,val in enumerate(row): t.setItem(r,c,QTableWidgetItem(val))

        t.setMinimumHeight(230); t.horizontalHeader().setStretchLastSection(True); return t

    def report_page(self):

        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Performance Report", self.export_pdf_report));

        g=QGridLayout(); g.setSpacing(12)

        self.report_crosshair_card = StatCard("CROSSHAIR SCORE", "N/A", "Analyze a VOD first", "⌖")
        self.report_aim_card = StatCard("AIM ACQUISITION", "N/A", "Analyze a VOD first", "⚡")
        self.report_export_card = StatCard("EXPORT", "Waiting", "Analyze a VOD first", "↓")

        for i, report_card in enumerate([
            self.report_crosshair_card,
            self.report_aim_card,
            self.report_export_card,
        ]):
            g.addWidget(report_card, 0, i)

        self.report_event_table = QTableWidget(0,5)
        self.report_event_table.setHorizontalHeaderLabels(
            ["#","TIME","EVENT","ROUND","DETAILS"]
        )
        self.report_event_table.verticalHeader().setVisible(False)
        self.report_event_table.setMinimumHeight(230)
        self.report_event_table.horizontalHeader().setStretchLastSection(True)

        lay.addLayout(g); lay.addWidget(self.coach_card()); lay.addWidget(self.report_event_table); return self.wrap(w)

    def heatmap_page(self):

        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Heatmap")); self.heatmap_view = HeatmapMock(); lay.addWidget(self.heatmap_view); lay.addWidget(label("Hot colors show where the player spent the most analyzed time on the in-game minimap.",14,MUTED)); return self.wrap(w)

    def compare_page(self):

        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(26,24,26,24); lay.addLayout(self.header("Match History")); lay.addWidget(label("Completed analyses are saved locally in SQLite.",14,MUTED))

        self.match_history_table = QTableWidget(0,7)
        self.match_history_table.setHorizontalHeaderLabels([
            "DATE", "VIDEO", "CROSSHAIR", "AIM", "MINIMAP", "DETECTIONS", "ROUNDS"
        ])
        self.match_history_table.verticalHeader().setVisible(False)
        self.match_history_table.setMinimumHeight(420)
        self.match_history_table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.match_history_table)
        self.refresh_match_history()
        return self.wrap(w)

    def refresh_match_history(self):
        if not hasattr(self, "match_history_table"):
            return

        rows = list_analyses(self.history_path)
        self.match_history_table.setRowCount(len(rows))
        for row_index, match in enumerate(rows):
            analyzed_at = str(match.get("analyzed_at", "")).replace("T", " ")
            video_name = Path(str(match.get("video_path", "Unknown"))).name
            values = [
                analyzed_at,
                video_name,
                _display_metric(match.get("crosshair_score"), "%"),
                _display_metric(match.get("aim_ms"), " ms"),
                _display_metric(match.get("minimap_coverage"), "%"),
                str(match.get("detections", 0)),
                str(match.get("rounds", 0)),
            ]
            for column, value in enumerate(values):
                self.match_history_table.setItem(
                    row_index, column, QTableWidgetItem(value)
                )

    def refresh_dashboard(self):
        if not hasattr(self, "dashboard_latest_label"):
            return

        rows = list_analyses(self.history_path, limit=1)
        if not rows:
            self.dashboard_latest_label.setText("No completed analysis yet.")
            return

        latest = rows[0]
        analyzed_at = str(latest.get("analyzed_at", "")).replace("T", " ")
        video_name = Path(str(latest.get("video_path", "Unknown"))).name
        self.dashboard_latest_label.setText(
            f"Latest: {video_name}  •  {analyzed_at}"
        )
        self.dashboard_aim.set_value(
            _display_metric(latest.get("aim_ms"), " ms"),
            f"{latest.get('encounters', 0)} detected encounters",
        )
        self.dashboard_crosshair.set_value(
            _display_metric(latest.get("crosshair_score"), "%"),
            "Crosshair placement score",
        )
        self.dashboard_minimap.set_value(
            _display_metric(latest.get("minimap_coverage"), "%"),
            "Player-marker coverage",
        )
        self.dashboard_detections.set_value(
            str(latest.get("detections", 0)),
            "Model detections",
        )
        self.dashboard_rounds.set_value(
            str(latest.get("rounds", 0)),
            "Analyzed rounds",
        )

    def setting_row(self, title, widget, hint=""):

        row = QFrame(); row.setObjectName("Card"); row.setMinimumHeight(82)

        lay = QHBoxLayout(row); lay.setContentsMargins(18, 12, 18, 12); lay.setSpacing(18)

        left = QVBoxLayout(); left.addWidget(label(title, 13, TEXT, True))

        if hint:

            left.addWidget(label(hint, 11, MUTED))

        lay.addLayout(left, 1)

        widget.setMinimumWidth(260); widget.setMaximumWidth(420)

        lay.addWidget(widget, 1)

        return row

    def combo(self, items, current=0):

        c = QComboBox(); c.addItems(items); c.setCurrentIndex(current); return c

    def settings_page(self):

        w = QWidget()

        lay = QVBoxLayout(w)

        lay.setContentsMargins(26, 24, 26, 24)

        lay.setSpacing(14)

        top = QHBoxLayout()

        title_box = QVBoxLayout()

        title_box.addWidget(label("Settings", 24, TEXT, True))

        title_box.addWidget(label("Customize FPSights for the senior project demo.", 14, MUTED))

        top.addLayout(title_box)

        top.addStretch()

        save_top = QPushButton("Save Settings")

        save_top.setObjectName("Primary")

        top.addWidget(save_top)

        lay.addLayout(top)

        profile = QFrame(); profile.setObjectName("CardHot")

        p_lay = QVBoxLayout(profile); p_lay.setContentsMargins(18, 14, 18, 14)

        p_lay.addWidget(label("PLAYER PROFILE", 13, RED, True))

        p_lay.addWidget(label("These settings are used for match records, reports, and dashboard display.", 12, MUTED))

        lay.addWidget(profile)

        grid = QGridLayout(); grid.setSpacing(12)

        player = QLineEdit("Bryan")

        game = self.combo(["Valorant", "Counter-Strike 2 / CS2"], 0)

        rank = self.combo(["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal 1", "Immortal 2", "Immortal 3", "Radiant"], 9)

        agent = self.combo(["Raze", "Jett", "Reyna", "Phoenix", "Sova", "Killjoy", "Cypher", "Omen", "Sage", "Other"], 0)

        default_map = self.combo(["Ascent", "Bind", "Haven", "Split", "Lotus", "Sunset", "Icebox", "Breeze", "Mirage", "Dust II", "Inferno"], 0)

        theme = self.combo(["Dark Valorant", "Midnight Blue", "Minimal Dark"], 0)

        accent = self.combo(["Valorant Red", "Neon Cyan", "Electric Purple", "Gold"], 0)

        target = self.combo(["250 ms", "300 ms", "350 ms", "400 ms", "450 ms"], 2)

        export_fmt = self.combo(["PDF Report", "CSV Data", "PDF + CSV", "Screenshot Summary"], 0)

        grid.addWidget(self.setting_row("Player Name", player, "Name shown on report and dashboard"), 0, 0)

        grid.addWidget(self.setting_row("Game", game, "Choose target FPS game"), 0, 1)

        grid.addWidget(self.setting_row("Rank", rank, "Player rank for profile card"), 1, 0)

        grid.addWidget(self.setting_row("Main Agent", agent, "Used for Valorant-style profile"), 1, 1)

        grid.addWidget(self.setting_row("Default Map", default_map, "Default map for demo analysis"), 2, 0)

        grid.addWidget(self.setting_row("Theme Mode", theme, "Visual style of the application"), 2, 1)

        grid.addWidget(self.setting_row("Accent Color", accent, "Highlight color for buttons and charts"), 3, 0)

        grid.addWidget(self.setting_row("Target Reaction Time", target, "Benchmark for good reaction time"), 3, 1)

        grid.addWidget(self.setting_row("Export Report Format", export_fmt, "Output format for final report"), 4, 0)

        save = QPushButton("Save Settings")

        save.setObjectName("Primary")

        save.setMinimumHeight(46)

        grid.addWidget(save, 4, 1)

        lay.addLayout(grid)

        note = QFrame(); note.setObjectName("Card")

        n = QVBoxLayout(note); n.setContentsMargins(18, 14, 18, 14)

        n.addWidget(label("WEEK 3 UI CONNECTION", 13, RED, True))

        n.addWidget(label("Next step: connect these settings to SQLite, so player profile and default options can be saved and loaded.", 12, MUTED))

        lay.addWidget(note)

        lay.addStretch()

        return self.wrap(w)

if __name__ == "__main__":

    app=QApplication(sys.argv); app.setStyleSheet(STYLE); win=FPSightsPro(); win.show(); sys.exit(app.exec())
