"""Single-page FPSights desktop UI connected to the existing analysis pipeline."""

import json
import sys
from datetime import datetime
from pathlib import Path
from sqlite3 import Error as DatabaseError

from PySide6.QtCore import Qt, QObject, QRect, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer, QVideoSink
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
from src.reporting import simple_coaching, generate_pdf_report
from src.settings import DEFAULT_CONFIDENCE, DEFAULT_FRAME_SKIP, DEFAULT_SAMPLE_RATE

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
        self.setMinimumHeight(150)

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
        pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
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
    status = Signal(str)
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
                self.config, progress=self.progress.emit, status=self.status.emit
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
        self.selected_model = self.find_model_path()
        self.analysis_thread = None
        self.analysis_worker = None
        self.last_analysis_result = None
        self.history_rows = []
        self.lesson_video_path = None
        self.lesson_start_ms = 0
        self.lesson_end_ms = 0
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
        self.build_lesson_section(page_layout)
        self.build_heatmap_section(page_layout)
        self.build_event_section(page_layout)
        self.build_history_section(page_layout)
        self.refresh_match_history()

    def build_brand(self, layout):
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedHeight(100)
        pixmap = QPixmap(str(LOGO_PATH))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
        model_row = QHBoxLayout()
        self.model_label = label(
            f"Model: {self.selected_model.name}" if self.selected_model else "No model selected: segmentation only", 11, MUTED
        )
        self.choose_model_button = QPushButton("Choose Model")
        self.choose_model_button.clicked.connect(self.choose_model)
        model_row.addWidget(self.model_label, 1)
        model_row.addWidget(self.choose_model_button)
        box_layout.addLayout(model_row)
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
        self.open_saved_button = QPushButton("Open Saved Analysis")
        self.open_saved_button.clicked.connect(self.choose_saved_analysis)
        actions.addWidget(self.open_saved_button)
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
        self.result_label = label("Analyze a video or open a saved analysis", 13, MUTED)
        heading_copy.addWidget(title)
        heading_copy.addWidget(self.result_label)
        heading.addLayout(heading_copy, 1)
        self.export_report_button = QPushButton("Export Report")
        self.export_report_button.setEnabled(False)
        self.export_report_button.clicked.connect(self.export_pdf_report)
        heading.addWidget(self.export_report_button, alignment=Qt.AlignBottom)
        layout.addLayout(heading)

        stats = QGridLayout()
        stats.setSpacing(12)
        self.aim_card = StatCard("AIM ALIGNMENT TIME", "N/A", "Measured encounters only", "⚡")
        self.crosshair_card = StatCard("HEAD OFFSET", "N/A", "Estimated from enemy boxes", "⌖")
        self.positioning_card = StatCard("MINIMAP MARKER COVERAGE", "N/A", "Tracking coverage only", "◎")
        self.aim_card.setToolTip("Time from first confirmed enemy detection to estimated head-area alignment. Not shot reaction time.")
        self.crosshair_card.setToolTip("Distance from screen-center crosshair to an estimated head point inside a detected enemy box. Not shooting accuracy or a grade.")
        self.positioning_card.setToolTip("Share of sampled gameplay frames where a POV marker was found on the minimap. Not positioning skill.")
        for column, card in enumerate([self.aim_card, self.crosshair_card, self.positioning_card]):
            stats.addWidget(card, 0, column)
            stats.setColumnStretch(column, 1)
        layout.addLayout(stats)
        layout.addWidget(label(
            "Crosshair uses screen centre and an estimated head area. Alignment measures reaching that area, not firing a shot. Inspect the video before acting on a suggestion.",
            11, MUTED,
        ))


    def build_lesson_section(self, layout):
        layout.addWidget(section_title("Coaching report"))
        lesson_card = QFrame()
        lesson_card.setObjectName("CardHot")
        lesson_layout = QVBoxLayout(lesson_card)
        lesson_layout.setContentsMargins(20, 16, 20, 16)
        lesson_layout.setSpacing(10)
        self.lesson_title = label("Analyze a video to see your coaching report.", 18, TEXT, True)
        self.lesson_summary = label("", 12, MUTED)
        self.lesson_practice = label("", 12, GREEN)
        lesson_layout.addWidget(self.lesson_title)
        lesson_layout.addWidget(self.lesson_summary)
        lesson_layout.addWidget(self.lesson_practice)
        self.lesson_examples_layout = QVBoxLayout()
        lesson_layout.addLayout(self.lesson_examples_layout)
        self.lesson_player = QMediaPlayer(self)
        self.lesson_audio = QAudioOutput(self)
        # Video playback should also work on computers without an audio device.
        if not QMediaDevices.defaultAudioOutput().isNull():
            self.lesson_player.setAudioOutput(self.lesson_audio)
        self.lesson_video = QLabel()
        self.lesson_video.setAlignment(Qt.AlignCenter)
        self.lesson_video.setMaximumHeight(500)
        self.lesson_video.setMinimumHeight(320)
        self.lesson_video.hide()
        # Display decoded frames directly; no GPU video widget is required.
        self.lesson_sink = QVideoSink(self)
        self.lesson_sink.videoFrameChanged.connect(self.show_video_frame)
        self.lesson_player.setVideoSink(self.lesson_sink)
        self.lesson_player.positionChanged.connect(self.stop_lesson_at_end)
        self.lesson_player.mediaStatusChanged.connect(self.lesson_media_ready)
        lesson_layout.addWidget(self.lesson_video)
        self.lesson_playback_label = label("", 11, MUTED)
        lesson_layout.addWidget(self.lesson_playback_label)
        self.pause_lesson_button = QPushButton("Pause / Resume")
        self.pause_lesson_button.setEnabled(False)
        self.pause_lesson_button.clicked.connect(self.toggle_lesson_playback)
        lesson_layout.addWidget(self.pause_lesson_button, alignment=Qt.AlignLeft)
        layout.addWidget(lesson_card)

    def show_lesson(self, result):
        self.lesson_player.stop()
        self.lesson_end_ms = 0
        self.pause_lesson_button.setEnabled(False)
        self.lesson_video.hide()
        self.lesson_playback_label.setText("")
        while self.lesson_examples_layout.count():
            item = self.lesson_examples_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        video_path = Path(str((result.get("video") or {}).get("path", "")))
        self.lesson_video_path = video_path if video_path.is_file() else None
        self.lesson_title.setText("Crosshair placement and gunfight practice")
        self.lesson_summary.setText("\n\n".join(simple_coaching(result)))
        self.lesson_practice.setText("")

    def play_lesson(self, example):
        clip_path = Path(str(example.get("clip_path", "")))
        use_clip = clip_path.is_file()
        if not use_clip and self.lesson_video_path is None:
            return
        self.lesson_player.stop()
        self.lesson_start_ms = 0 if use_clip else int(example["start_ms"])
        self.lesson_end_ms = (
            int(example["end_ms"]) - int(example["start_ms"])
            if use_clip else int(example["end_ms"])
        )
        self.lesson_video.show()
        self.pause_lesson_button.setEnabled(True)
        self.lesson_playback_label.setText("Playing footage from the original VOD.")
        source = QUrl.fromLocalFile(str(clip_path if use_clip else self.lesson_video_path))
        if self.lesson_player.source() != source:
            self.lesson_player.setSource(source)
        else:
            self.lesson_player.setPosition(self.lesson_start_ms)
            self.lesson_player.play()

    def show_video_frame(self, frame):
        if frame.isValid():
            pixmap = QPixmap.fromImage(frame.toImage())
            self.lesson_video.setPixmap(pixmap.scaled(self.lesson_video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def toggle_lesson_playback(self):
        if self.lesson_player.playbackState() == QMediaPlayer.PlayingState:
            self.lesson_player.pause()
        else:
            if self.lesson_player.position() >= self.lesson_end_ms:
                self.lesson_player.setPosition(self.lesson_start_ms)
            self.lesson_player.play()

    def lesson_media_ready(self, status):
        if status == QMediaPlayer.LoadedMedia and self.lesson_video.isVisible():
            self.lesson_player.setPosition(self.lesson_start_ms)
            self.lesson_player.play()
        elif status == QMediaPlayer.InvalidMedia:
            self.lesson_playback_label.setText("This video could not be played. Check the original file and codec.")

    def stop_lesson_at_end(self, position):
        if self.lesson_end_ms and position >= self.lesson_end_ms:
            self.lesson_player.pause()

    def build_heatmap_section(self, layout):
        layout.addWidget(section_title("POV minimap activity"))
        self.analysis_heatmap = HeatmapView()
        layout.addWidget(self.analysis_heatmap)
        layout.addWidget(label("Warmer areas contain more marker observations. Approximate minimap coordinates; rotating maps can distort this view.", 11, MUTED))
        layout.addWidget(label("Hot colors show detected POV-marker locations, including possible spectated teammates. Alive state and player identity are not verified. A fixed minimap is needed to interpret these as map locations.", 12, MUTED))

    def build_event_section(self, layout):
        layout.addWidget(section_title("Detected events"))
        self.analysis_event_table = QTableWidget(0, 5)
        self.analysis_event_table.setHorizontalHeaderLabels(["#", "TIME", "EVENT", "ROUND", "DETAILS"])
        self.analysis_event_table.setMinimumHeight(230)
        self.configure_table(self.analysis_event_table, 4)
        self.analysis_event_table.cellDoubleClicked.connect(self.play_event)
        layout.addWidget(self.analysis_event_table)
        layout.addWidget(label("Double-click an event to inspect that moment in the original video.", 11, MUTED))

    def build_history_section(self, layout):
        history_header = QHBoxLayout()
        history_header.addWidget(section_title("Recent analyses"))
        history_header.addStretch()
        history_header.addWidget(label("Saved locally", 11, MUTED))
        layout.addLayout(history_header)
        self.match_history_table = QTableWidget(0, 7)
        self.match_history_table.setHorizontalHeaderLabels(["DATE", "VIDEO", "PROXIMITY", "ALIGNMENT", "MARKER COVERAGE", "DETECTIONS", "ROUNDS"])
        self.match_history_table.setMinimumHeight(250)
        self.configure_table(self.match_history_table, 1)
        self.match_history_table.cellDoubleClicked.connect(self.load_saved_analysis)
        layout.addWidget(self.match_history_table)
        layout.addWidget(label("Double-click a saved analysis to reopen its report.", 11, MUTED))

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
        if self.analysis_thread is not None:
            return
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

    def choose_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose trained enemy model", str(PROJECT_ROOT / "models"), "YOLO Weights (*.pt)")
        if path:
            self.selected_model = Path(path)
            self.model_label.setText(f"Model: {self.selected_model.name}")

    def choose_saved_analysis(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a saved analysis", str(PROJECT_ROOT / "output"), "Analysis (run.json)")
        if path:
            self.open_saved_analysis(Path(path))

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = PROJECT_ROOT / "output" / self.selected_video.stem / timestamp
        model_path = self.selected_model
        config = ProcessingConfig(
            video_path=self.selected_video, output_dir=output_dir, model_path=model_path,
            confidence=DEFAULT_CONFIDENCE,
            frame_skip=DEFAULT_FRAME_SKIP,
            sample_rate=DEFAULT_SAMPLE_RATE,
            device="cpu" if model_path is not None else None,
            preview=False, review_video=model_path is not None,
        )
        self.choose_vod_button.setEnabled(False)
        self.choose_model_button.setEnabled(False)
        self.open_saved_button.setEnabled(False)
        self.export_report_button.setEnabled(False)
        self.lesson_player.stop()
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
        self.analysis_worker.status.connect(self.analysis_status_label.setText)
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
        """Save a new run, then use the same display flow as history playback."""
        self.display_analysis(result)
        try:
            save_analysis(self.history_path, result)
            self.refresh_match_history()
        except (OSError, ValueError, DatabaseError) as error:
            # Keep the analysis visible even if local history cannot be written.
            self.analysis_status_label.setText(f"Analysis ready; history could not be saved: {error}")

    def display_analysis(self, result):
        self.last_analysis_result = result
        video = result.get("video") or {}
        duration = video.get("duration_ms", 0) / 60000
        frames = (result.get("detection") or {}).get("processed_frames", 0)
        live_seconds = (result.get("segmentation") or {}).get("analyzable_duration_ms", 0) / 1000
        self.result_label.setText(f"{Path(video.get('path', 'Unknown video')).name} · {duration:.1f} min source · {live_seconds:.1f}s live ranges · {frames:,} sampled frames")
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(100)
        analytics = result.get("analytics") or {}
        crosshair = analytics.get("crosshair") or {}
        aim = analytics.get("aim_reaction") or {}
        positioning = analytics.get("positioning") or {}

        score = crosshair.get("score_percent")
        head_error = crosshair.get("mean_head_error_px")
        evaluated_frames = crosshair.get("evaluated_frames", 0)
        if isinstance(head_error, (int, float)):
            self.crosshair_card.set_value(f"{head_error:.1f}px", f"Estimated head offset · {evaluated_frames} frames")
        else:
            self.crosshair_card.set_value("N/A", "No confirmed enemy frames to measure")

        aim_ms = aim.get("average_ms")
        measured = aim.get("measured_encounters", 0)
        encounters = aim.get("encounters", 0)
        if isinstance(aim_ms, (int, float)):
            self.aim_card.set_value(f"{aim_ms:.0f} ms", f"Measured subset: {measured}/{encounters} encounters")
        else:
            self.aim_card.set_value("N/A", f"Measured subset: {measured}/{encounters} encounters")

        samples = positioning.get("sample_count", 0)
        coverage = positioning.get("coverage_percent")
        if isinstance(coverage, (int, float)) and samples:
            self.positioning_card.set_value(f"{coverage:.1f}%", f"Marker found in {samples} sampled frames")
        else:
            self.positioning_card.set_value("N/A", "Player marker not detected")

        self.load_real_events(result)
        self.show_lesson(result)
        heatmap_path = result.get("artifacts", {}).get("heatmap")
        # Always reset the image so an empty run cannot show a previous heatmap.
        self.analysis_heatmap.set_image(heatmap_path)
        review_path = result.get("artifacts", {}).get("review_video")
        self.open_review_button.setEnabled(bool(review_path and Path(review_path).exists()))
        self.export_report_button.setEnabled(True)
        if result.get("status") == "stopped" or result.get("limited_run"):
            message = "Partial analysis: only the processed frames are included."
        elif not analytics:
            message = "Segmentation complete. Add trained weights to generate enemy analytics."
        elif not result.get("segmentation", {}).get("analyzable_duration_ms"):
            message = "No live gameplay found. Try a clear Valorant recording."
        else:
            message = "Analysis ready. Review the moments below, or export your report."
        self.analysis_status_label.setText(message)

    def load_real_events(self, result):
        self.analysis_event_table.setRowCount(0)
        self.current_events = []
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
        self.current_events = events
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

    def play_event(self, row, _column):
        if not 0 <= row < len(self.current_events) or self.lesson_video_path is None:
            return
        timestamp = int(self.current_events[row]["timestamp_ms"])
        self.play_lesson({"start_ms": max(0, timestamp - 2000), "end_ms": timestamp + 4000})

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
        self.history_rows = rows
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

    def load_saved_analysis(self, row, _column):
        if 0 <= row < len(self.history_rows):
            self.open_saved_analysis(Path(self.history_rows[row]["run_path"]) / "run.json")

    def open_saved_analysis(self, run_path):
        """Read saved results without recomputing or changing the source run."""
        if self.analysis_thread is not None:
            return
        try:
            result = json.loads(run_path.read_text(encoding="utf-8"))
            if not isinstance(result, dict) or result.get("schema_version") != 1 or not isinstance(result.get("video"), dict):
                raise ValueError("Choose a valid FPSights run.json file.")
            # Prefer artifacts beside run.json when an analysis folder was moved.
            artifacts = result.setdefault("artifacts", {})
            if not isinstance(artifacts, dict):
                raise ValueError("The saved artifact list is invalid.")
            for key, filename in {
                "segments": "segments.json", "metrics": "metrics.json",
                "detections": "detections.json", "heatmap": "heatmap.png",
                "positioning": "positioning.json", "review_video": "review.mp4",
                "lessons": "lessons.json",
            }.items():
                local_path = run_path.parent / filename
                if local_path.is_file():
                    artifacts[key] = str(local_path.resolve())
            if artifacts.get("lessons") and Path(artifacts["lessons"]).is_file():
                result["lessons"] = json.loads(Path(artifacts["lessons"]).read_text(encoding="utf-8"))
            for index, example in enumerate((result.get("lessons") or {}).get("examples", []), 1):
                clip = run_path.parent / f"lesson-{index:02d}.mp4"
                if clip.is_file():
                    example["clip_path"] = str(clip.resolve())
            self.display_analysis(result)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            QMessageBox.warning(self, "Could Not Open Analysis", str(error))

    def closeEvent(self, event):
        # Qt must keep the worker thread alive until processing has finished.
        if self.analysis_thread is not None:
            QMessageBox.information(self, "Analysis Running", "Wait for analysis to finish before closing FPSights.")
            event.ignore()
            return
        self.lesson_player.stop()
        super().closeEvent(event)

    @Slot(str)
    def analysis_failed(self, error):
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        self.analysis_status_label.setText(f"Analysis failed: {error}")
        QMessageBox.critical(self, "FPSights Analysis Error", error)

    @Slot()
    def analysis_finished(self):
        self.choose_vod_button.setEnabled(True)
        self.choose_model_button.setEnabled(True)
        self.open_saved_button.setEnabled(True)
        self.export_report_button.setEnabled(self.last_analysis_result is not None)
        self.start_analysis_button.setEnabled(self.selected_video is not None)
        self.analysis_worker = None
        self.analysis_thread = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = FPSightsPro()
    window.show()
    sys.exit(app.exec())
