"""Single-page FPSights desktop UI connected to the existing analysis pipeline."""

import json
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QRect, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSET_DIR / "fpsights-logo-white.png"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.history import initialize_history, list_analyses, save_analysis
from src.pipeline.processor import ProcessingConfig, process_video
from src.reporting import coaching_recommendations, generate_pdf_report

BG = "#070d14"
PANEL = "#0d1722"
PANEL2 = "#111e2c"
BORDER = "#22384e"
TEXT = "#f4f7fb"
MUTED = "#9fb3c8"
RED = "#ff375f"
GREEN = "#20e080"

STYLE = f"""
QMainWindow, QWidget#AppRoot, QWidget#Page {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-family: "Helvetica Neue", Arial; font-size: 14px; }}
QScrollArea#PageScroll {{ background: {BG}; border: none; }}
QScrollArea#PageScroll > QWidget > QWidget {{ background: {BG}; }}
QFrame#Card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#CardHot {{ background: #120d16; border: 1px solid {RED}; border-radius: 12px; }}
QFrame#ImportBox {{ background: #0a131d; border: 2px dashed #36506b; border-radius: 14px; }}
QFrame#ImportBox[dragActive="true"] {{ background: #15101a; border-color: {RED}; }}
QPushButton {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 11px 18px; font-weight: bold; }}
QPushButton:hover {{ border-color: {RED}; background: #172538; }}
QPushButton#Primary {{ background-color: {RED}; color: white; border-color: {RED}; }}
QPushButton#Primary:hover {{ background-color: #ff5575; border-color: #ff5575; }}
QPushButton:disabled {{ background: #111a24; color: #607487; border-color: #1a2b3b; }}
QPushButton#Primary:disabled {{ background-color: #24141c; color: #725160; border-color: #3b2230; }}
QProgressBar {{ background: #070d14; border: 1px solid {BORDER}; border-radius: 6px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 6px; }}
QTableWidget {{ background: #08111b; alternate-background-color: #0b1520; gridline-color: #1e3145; border: 1px solid {BORDER}; border-radius: 8px; selection-background-color: #3b1220; selection-color: {TEXT}; }}
QHeaderView::section {{ background: {PANEL2}; color: {TEXT}; padding: 8px; border: none; font-weight: bold; }}
QScrollBar:vertical {{ background: #08111b; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #29435b; min-height: 28px; border-radius: 5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def label(text, size=12, color=TEXT, bold=False):
    widget = QLabel(text)
    weight = "font-weight:bold;" if bold else ""
    widget.setStyleSheet(f"color:{color}; font-size:{size}px;{weight}")
    widget.setWordWrap(True)
    return widget


def section_title(text):
    return label(text.upper(), 11, MUTED, True)


def _display_metric(value, suffix):
    return f"{value:.1f}{suffix}" if isinstance(value, (int, float)) else "N/A"


class VideoDropBox(QFrame):
    """Presentation-layer shortcut to the existing video selection flow."""

    video_dropped = Signal(str)
    SUPPORTED_SUFFIXES = {".mp4", ".mkv", ".mov"}

    def __init__(self):
        super().__init__()
        self.setObjectName("ImportBox")
        self.setProperty("dragActive", False)
        self.setAcceptDrops(True)
        self.setMinimumHeight(170)

    def _set_drag_active(self, active):
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        valid = any(Path(url.toLocalFile()).suffix.lower() in self.SUPPORTED_SUFFIXES for url in urls)
        if valid:
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drag_active(False)
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                self.video_dropped.emit(str(path))
                event.acceptProposedAction()
                return
        event.ignore()


class HeatmapView(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(400)
        self.setObjectName("Card")
        self.heatmap_pixmap = None

    def set_image(self, image_path):
        pixmap = QPixmap(str(image_path))
        self.heatmap_pixmap = pixmap if not pixmap.isNull() else None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.heatmap_pixmap is not None:
            target = QRect(18, 18, self.width() - 36, self.height() - 36)
            scaled = self.heatmap_pixmap.scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = target.x() + (target.width() - scaled.width()) // 2
            y = target.y() + (target.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            return
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, "Run an analysis to generate a heatmap")


class StatCard(QFrame):
    def __init__(self, title, value, sub, icon="◇"):
        super().__init__()
        self.setObjectName("Card")
        self.setMinimumHeight(112)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(14)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color:{RED}; font-size:28px;")
        layout.addWidget(icon_label)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        copy.addWidget(label(title, 10, MUTED, True))
        self.value_label = label(value, 24, TEXT, True)
        self.sub_label = label(sub, 11, GREEN, True)
        copy.addWidget(self.value_label)
        copy.addWidget(self.sub_label)
        layout.addLayout(copy, 1)

    def set_value(self, value, sub=""):
        self.value_label.setText(str(value))
        self.sub_label.setText(str(sub))


class AnalysisWorker(QObject):
    """Run the existing FPSights processor without freezing the UI."""

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
            result = process_video(self.config, progress=lambda done, total: self.progress.emit(done, total))
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
        self.history_path = PROJECT_ROOT / "output" / "fpsights-history.sqlite"
        initialize_history(self.history_path)
        self.setWindowTitle("FPSights — VOD Analysis")
        self.resize(1280, 900)
        self.setMinimumSize(980, 700)
        self.setStyleSheet(STYLE)

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet(f"background: {BG};")
        root_layout.addWidget(scroll)
        page = QWidget()
        page.setObjectName("Page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(42, 30, 42, 48)
        page_layout.setSpacing(18)
        scroll.setWidget(page)
        self.setCentralWidget(root)

        self.build_brand(page_layout)
        self.build_import_section(page_layout)
        self.build_analysis_dashboard(page_layout)
        self.build_heatmap_section(page_layout)
        self.build_event_section(page_layout)
        self.build_history_section(page_layout)
        self.refresh_match_history()

    def build_brand(self, layout):
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedHeight(190)
        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("FPSights")
            logo.setStyleSheet(f"color:{TEXT}; font-size:34px; font-weight:bold;")
        layout.addWidget(logo, alignment=Qt.AlignHCenter)
        tagline = label("TURN GAMEPLAY INTO BETTER DECISIONS", 11, MUTED, True)
        tagline.setAlignment(Qt.AlignCenter)
        layout.addWidget(tagline)

    def build_import_section(self, layout):
        self.import_box = VideoDropBox()
        self.import_box.video_dropped.connect(self.set_selected_video)
        box_layout = QVBoxLayout(self.import_box)
        box_layout.setContentsMargins(28, 22, 28, 22)
        box_layout.setSpacing(10)
        import_title = label("Import gameplay video", 18, TEXT, True)
        import_title.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(import_title)
        self.selected_video_label = label("Drop a video here or choose a file", 13, MUTED)
        self.selected_video_label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(self.selected_video_label)
        self.choose_vod_button = QPushButton("Choose Video")
        self.choose_vod_button.clicked.connect(self.choose_video)
        box_layout.addWidget(self.choose_vod_button, alignment=Qt.AlignHCenter)
        layout.addWidget(self.import_box)

        actions = QHBoxLayout()
        actions.addStretch()
        self.start_analysis_button = QPushButton("Analyze Video")
        self.start_analysis_button.setObjectName("Primary")
        self.start_analysis_button.setEnabled(False)
        self.start_analysis_button.clicked.connect(self.start_analysis)
        self.open_review_button = QPushButton("Open Review Video")
        self.open_review_button.setEnabled(False)
        self.open_review_button.clicked.connect(self.open_review_video)
        actions.addWidget(self.start_analysis_button)
        actions.addWidget(self.open_review_button)
        actions.addStretch()
        layout.addLayout(actions)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 12, 18, 12)
        self.analysis_status_label = label("Choose a gameplay video to begin.", 12, MUTED)
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        self.analysis_progress.setTextVisible(False)
        status_layout.addWidget(self.analysis_status_label)
        status_layout.addWidget(self.analysis_progress)
        layout.addWidget(status_card)

    def build_analysis_dashboard(self, layout):
        heading = QHBoxLayout()
        heading_copy = QVBoxLayout()
        title = label("Analysis dashboard", 24, TEXT, True)
        title.setWordWrap(False)
        subtitle = label("Your latest completed video analysis", 13, MUTED)
        subtitle.setWordWrap(False)
        heading_copy.addWidget(title)
        heading_copy.addWidget(subtitle)
        heading.addLayout(heading_copy, 1)
        self.export_report_button = QPushButton("Export Report")
        self.export_report_button.setEnabled(False)
        self.export_report_button.clicked.connect(self.export_pdf_report)
        heading.addWidget(self.export_report_button, alignment=Qt.AlignBottom)
        layout.addLayout(heading)

        stats = QGridLayout()
        stats.setSpacing(12)
        self.aim_card = StatCard("AIM ACQUISITION", "N/A", "Waiting for analysis", "⚡")
        self.crosshair_card = StatCard("CROSSHAIR SCORE", "N/A", "Waiting for analysis", "⌖")
        self.positioning_card = StatCard("POSITIONING", "N/A", "Waiting for analysis", "◎")
        for column, card in enumerate([self.aim_card, self.crosshair_card, self.positioning_card]):
            stats.addWidget(card, 0, column)
            stats.setColumnStretch(column, 1)
        layout.addLayout(stats)

        coaching = QFrame()
        coaching.setObjectName("CardHot")
        coaching_layout = QVBoxLayout(coaching)
        coaching_layout.setContentsMargins(20, 16, 20, 16)
        coaching_layout.setSpacing(8)
        coaching_layout.addWidget(label("COACHING REPORT", 12, RED, True))
        self.coach_feedback_labels = []
        for placeholder in ["Analyze a VOD to generate coaching feedback.", "", ""]:
            feedback = label(placeholder, 12, TEXT)
            self.coach_feedback_labels.append(feedback)
            coaching_layout.addWidget(feedback)
        layout.addWidget(coaching)

    def build_heatmap_section(self, layout):
        layout.addWidget(section_title("Position heatmap"))
        self.analysis_heatmap = HeatmapView()
        layout.addWidget(self.analysis_heatmap)
        layout.addWidget(label("Hot colors show where the tracked player marker appeared most often on the in-game minimap. Coverage depends on successful marker detection.", 12, MUTED))

    def build_event_section(self, layout):
        layout.addWidget(section_title("Detected events"))
        self.analysis_event_table = QTableWidget(0, 5)
        self.analysis_event_table.setHorizontalHeaderLabels(["#", "TIME", "EVENT", "ROUND", "DETAILS"])
        self.analysis_event_table.setMinimumHeight(230)
        self.configure_table(self.analysis_event_table, 4)
        layout.addWidget(self.analysis_event_table)

    def build_history_section(self, layout):
        history_header = QHBoxLayout()
        history_header.addWidget(section_title("Recent analyses"))
        history_header.addStretch()
        history_header.addWidget(label("Saved locally", 11, MUTED))
        layout.addLayout(history_header)
        self.match_history_table = QTableWidget(0, 7)
        self.match_history_table.setHorizontalHeaderLabels(["DATE", "VIDEO", "CROSSHAIR", "AIM", "MINIMAP", "DETECTIONS", "ROUNDS"])
        self.match_history_table.setMinimumHeight(250)
        self.configure_table(self.match_history_table, 1)
        layout.addWidget(self.match_history_table)

    def configure_table(self, table, stretch_column):
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)

    def choose_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose FPS Gameplay VOD", "", "Videos (*.mp4 *.mkv *.mov)")
        if file_path:
            self.set_selected_video(file_path)

    @Slot(str)
    def set_selected_video(self, file_path):
        self.selected_video = Path(file_path)
        self.selected_video_label.setText(self.selected_video.name)
        self.selected_video_label.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:bold;")
        self.analysis_status_label.setText("Video ready. Click Analyze Video to start processing.")
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        self.start_analysis_button.setEnabled(True)
        self.open_review_button.setEnabled(False)

    def find_model_path(self):
        model = PROJECT_ROOT / "models" / "fpsights-yolo11n-960.pt"
        return model if model.exists() else None

    def start_analysis(self):
        if self.selected_video is None:
            QMessageBox.warning(self, "No VOD Selected", "Please choose a gameplay video first.")
            return
        if not self.selected_video.exists():
            QMessageBox.critical(self, "Video Missing", "The selected video file no longer exists.")
            return
        if self.analysis_thread is not None:
            QMessageBox.information(self, "Analysis Running", "FPSights is already analyzing a video.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "output" / self.selected_video.stem / timestamp
        model_path = self.find_model_path()
        config = ProcessingConfig(
            video_path=self.selected_video, output_dir=output_dir, model_path=model_path,
            confidence=0.25, frame_skip=5, sample_rate=2.0,
            device="cpu" if model_path is not None else None,
            preview=False, review_video=model_path is not None,
        )
        self.choose_vod_button.setEnabled(False)
        self.start_analysis_button.setEnabled(False)
        self.open_review_button.setEnabled(False)
        self.analysis_progress.setRange(0, 0)
        if model_path is None:
            self.analysis_status_label.setText("Running segmentation... YOLO model not found, so detection metrics will be unavailable.")
        else:
            self.analysis_status_label.setText("Running segmentation and preparing enemy detection...")

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
        self.analysis_progress.setRange(0, 100)
        percent = max(0, min(100, round(done / total * 100) if total else 0))
        self.analysis_progress.setValue(percent)
        self.analysis_status_label.setText(f"Detecting enemies and computing metrics... {percent}%")

    @Slot(dict)
    def analysis_succeeded(self, result):
        self.last_analysis_result = result
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(100)
        analytics = result.get("analytics") or {}
        crosshair = analytics.get("crosshair") or {}
        aim = analytics.get("aim_reaction") or {}
        positioning = analytics.get("positioning") or {}

        score = crosshair.get("score_percent")
        head_error = crosshair.get("mean_head_error_px")
        evaluated_frames = crosshair.get("evaluated_frames", 0)
        if isinstance(score, (int, float)):
            error_text = f"{head_error:.1f}px" if isinstance(head_error, (int, float)) else "N/A"
            self.crosshair_card.set_value(f"{score:.1f}%", f"{evaluated_frames} frames • head error {error_text}")
        else:
            self.crosshair_card.set_value("N/A", "No YOLO crosshair result")

        aim_ms = aim.get("average_ms")
        measured = aim.get("measured_encounters", 0)
        encounters = aim.get("encounters", 0)
        if isinstance(aim_ms, (int, float)):
            self.aim_card.set_value(f"{aim_ms:.0f} ms", f"{measured}/{encounters} encounters measured")
        else:
            self.aim_card.set_value("N/A", f"{measured}/{encounters} encounters measured")

        samples = positioning.get("sample_count", 0)
        coverage = positioning.get("coverage_percent")
        if isinstance(coverage, (int, float)) and samples:
            self.positioning_card.set_value(f"{coverage:.1f}%", f"{samples} minimap samples")
        else:
            self.positioning_card.set_value("N/A", "Player marker not detected")

        self.load_real_events(result)
        self.update_coaching_feedback(result)
        save_analysis(self.history_path, result)
        self.refresh_match_history()
        heatmap_path = result.get("artifacts", {}).get("heatmap")
        if heatmap_path and Path(heatmap_path).exists():
            self.analysis_heatmap.set_image(heatmap_path)
        review_path = result.get("artifacts", {}).get("review_video")
        self.open_review_button.setEnabled(bool(review_path and Path(review_path).exists()))
        self.export_report_button.setEnabled(True)
        self.analysis_status_label.setText("Analysis complete." if analytics else "Segmentation complete. YOLO analytics were not generated.")

    def load_real_events(self, result):
        self.analysis_event_table.setRowCount(0)
        metrics_path = result.get("artifacts", {}).get("metrics")
        if not metrics_path or not Path(metrics_path).exists():
            return
        try:
            metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        events = metrics.get("events", [])
        if not isinstance(events, list):
            return
        self.analysis_event_table.setRowCount(len(events))
        for row, event in enumerate(events):
            timestamp_ms = event.get("timestamp_ms", 0)
            event_type = event.get("type", "unknown")
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
                detail = "Already aligned" if event["reaction_ms"] == 0 else f"{event['reaction_ms']} ms"
            values = [str(row + 1), time_text, str(event_type).replace("_", " ").title(), str(round_number if round_number is not None else "—"), detail]
            for column, value in enumerate(values):
                self.analysis_event_table.setItem(row, column, QTableWidgetItem(value))

    def update_coaching_feedback(self, result):
        analytics = result.get("analytics") or {}
        recommendations = coaching_recommendations(analytics.get("crosshair") or {}, analytics.get("aim_reaction") or {})
        for index, feedback in enumerate(self.coach_feedback_labels):
            if index < len(recommendations):
                feedback.setText(recommendations[index])
                feedback.show()
            else:
                feedback.hide()

    def open_review_video(self):
        if not self.last_analysis_result:
            return
        review_path = self.last_analysis_result.get("artifacts", {}).get("review_video")
        if not review_path or not Path(review_path).exists():
            QMessageBox.warning(self, "Review Video Missing", "No review video was produced for this analysis.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(review_path)))

    def export_pdf_report(self):
        if not self.last_analysis_result:
            QMessageBox.information(self, "No Analysis", "Analyze a VOD before exporting a report.")
            return
        metrics_path = self.last_analysis_result.get("artifacts", {}).get("metrics")
        default_directory = Path(metrics_path).parent if metrics_path else PROJECT_ROOT / "output"
        default_path = default_directory / "fpsights-report.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export FPSights Report", str(default_path), "PDF Files (*.pdf)")
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
        QMessageBox.information(self, "Report Exported", f"PDF report saved to:\n{output_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path)))

    def refresh_match_history(self):
        rows = list_analyses(self.history_path, limit=10)
        self.match_history_table.setRowCount(len(rows))
        for row_index, match in enumerate(rows):
            values = [
                str(match.get("analyzed_at", "")).replace("T", " "),
                Path(str(match.get("video_path", "Unknown"))).name,
                _display_metric(match.get("crosshair_score"), "%"),
                _display_metric(match.get("aim_ms"), " ms"),
                _display_metric(match.get("minimap_coverage"), "%"),
                str(match.get("detections", 0)), str(match.get("rounds", 0)),
            ]
            for column, value in enumerate(values):
                self.match_history_table.setItem(row_index, column, QTableWidgetItem(value))

    @Slot(str)
    def analysis_failed(self, error):
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        self.analysis_status_label.setText(f"Analysis failed: {error}")
        QMessageBox.critical(self, "FPSights Analysis Error", error)

    @Slot()
    def analysis_finished(self):
        self.choose_vod_button.setEnabled(True)
        self.start_analysis_button.setEnabled(self.selected_video is not None)
        self.analysis_worker = None
        self.analysis_thread = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = FPSightsPro()
    window.show()
    sys.exit(app.exec())
