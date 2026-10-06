from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from machine_vision import __version__
from machine_vision.camera.opencv_camera import CameraError, OpenCVCamera
from machine_vision.imaging.enhancement import crop_fraction
from machine_vision.imaging.focus import assess_focus, focus_peaking, is_acceptable
from machine_vision.models import Decision, InspectionResult, PackageDetection
from machine_vision.services.evidence import EvidenceWriter
from machine_vision.services.pipeline import FrameQualityError, VisionPipeline
from machine_vision.ui.asset_manifest import SceneManifest, load_scene_manifest
from machine_vision.ui.conveyor_panel import ConveyorPanel
from machine_vision.ui.digital_twin import DigitalTwinWidget, ProcessStage
from machine_vision.ui.logo_calibration import LogoCalibrationDialog

STYLE = """
QMainWindow, QWidget { background: #07111b; color: #d9e5f0;
                       font-family: "Segoe UI"; font-size: 12px; }
QFrame#panel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
               stop:0 #101d2a, stop:1 #0c1722); border: 1px solid #21364a;
               border-radius: 9px; }
QFrame#topbar { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #101f2e, stop:1 #0b1722); border: 1px solid #21364a;
                border-radius: 10px; }
QFrame#statusbar { background: #0b1722; border: 1px solid #20364a; border-radius: 12px; }
QFrame#subpanel { background: #0a151f; border: 1px solid #1d3143; border-radius: 8px; }
QLabel#title { font-size: 18px; font-weight: 700; color: #f3f7fb; letter-spacing: 1px; }
QLabel#subtitle { color: #7890a5; font-size: 10px; letter-spacing: 1px; }
QLabel#sectionTitle { color: #c0cfdb; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#metricTitle { color: #7890a5; font-size: 9px; font-weight: 700; letter-spacing: 1px; }
QLabel#metricValue { color: #f4f8fc; font-size: 20px; font-weight: 700; }
QLabel#metricUnit { color: #6f8497; font-size: 9px; }
QLabel#fieldName { color: #71879a; font-size: 10px; }
QLabel#fieldValue { color: #e1eaf2; font-weight: 600; }
QLabel#assetReady { color: #54c793; background: rgba(38,162,105,28); border-radius: 5px;
                    padding: 4px 7px; font-size: 10px; font-weight: 700; }
QLabel#assetWaiting { color: #e0ad47; background: rgba(210,153,34,28); border-radius: 5px;
                      padding: 4px 7px; font-size: 10px; font-weight: 700; }
QLabel#reasonBox { background: #09141f; color: #9eb0bf; border: 1px solid #1e3245;
                   border-radius: 6px; padding: 7px; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
              stop:0 #388cf5, stop:1 #2474d6); color: white; border: 1px solid #4b98f3;
              border-radius: 6px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #4897f4; border-color: #78b2f7; }
QPushButton:pressed { background: #1c67bd; }
QPushButton:disabled { background: #1a2a39; border-color: #263b4d; color: #5f7486; }
QPushButton#secondary { background: #142535; color: #bdcad5; border: 1px solid #2a4257; }
QPushButton#secondary:hover { background: #1b3043; border-color: #3b5a73; }
QPushButton#viewPreset { background: #102131; color: #aebdca; border: 1px solid #2a4257;
                         border-radius: 6px; padding: 6px 8px; font-size: 10px; }
QPushButton#viewPreset:hover { background: #183049; border-color: #48739a; color: #e6f1f9; }
QPushButton#viewPreset:checked { background: #1c5f98; border-color: #62aaf0; color: white; }
QTableWidget { background: #09141f; alternate-background-color: #0d1a26;
               gridline-color: transparent; border: 1px solid #21364a;
               border-radius: 7px; selection-background-color: #173e66; }
QHeaderView::section { background: #122333; color: #8499aa; padding: 7px;
                       border: 0; border-bottom: 1px solid #284055; font-size: 10px; }
QCheckBox { color: #a9bac8; spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QLineEdit, QSpinBox { background:#0b1722; color:#e1eaf2; border:1px solid #294157;
                       border-radius:5px; padding:5px; }
QTreeWidget { background: transparent; border: 0; color: #aebdca; outline: 0;
              alternate-background-color: #0d1a26; }
QTreeWidget::item { min-height: 27px; border-radius: 4px; }
QTreeWidget::item:hover { background: #102333; }
QTreeWidget::item:selected { background: #163a5d; color: #edf6ff; }
QSplitter::handle { background: transparent; width: 6px; }
QTabWidget::pane { border: 1px solid #21364a; background: #09141f; border-radius: 7px; }
QTabBar::tab { background: transparent; color: #758b9e; padding: 9px 18px;
               border: 0; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:hover { color: #b9c8d4; background: #0e1d2a; }
QTabBar::tab:selected { color: #eaf2f8; background: #102131; border-bottom: 2px solid #3b92f6; }
QTabWidget#inspectorTabs QTabBar::tab { padding: 7px 8px; font-size: 9px; }
QSlider::groove:horizontal { height: 4px; background: #1b3042; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #287edc; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #63a9f7;
                             border: 1px solid #a2cef9; border-radius: 7px; }
QScrollBar:vertical { background: #09141f; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #294157; min-height: 28px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class VideoCanvas(QLabel):
    def __init__(self) -> None:
        super().__init__("CAMERA OFFLINE\nChọn KẾT NỐI CAMERA để bắt đầu")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#05090d; border:1px solid #263542; color:#607283;")

    def show_frame(self, frame: np.ndarray, roi: list[float] | None = None) -> None:
        display = frame.copy()
        if roi:
            h, w = display.shape[:2]
            x, y, rw, rh = roi
            p1 = (int(x * w), int(y * h))
            p2 = (int((x + rw) * w), int((y + rh) * h))
            cv2.rectangle(display, p1, p2, (45, 210, 140), 3)
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        image = QImage(rgb.data, w, h, channels * w, QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)


class MetricCard(QFrame):
    def __init__(
        self, title: str, value: str = "—", unit: str = "", accent: str = "#3b92f6"
    ) -> None:
        super().__init__()
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 8)
        layout.setSpacing(1)
        accent_bar = QFrame()
        accent_bar.setFixedHeight(3)
        accent_bar.setStyleSheet(f"background:{accent}; border-radius:1px;")
        label = QLabel(title)
        label.setObjectName("metricTitle")
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.unit = QLabel(unit)
        self.unit.setObjectName("metricUnit")
        layout.addWidget(accent_bar)
        layout.addSpacing(3)
        layout.addWidget(label)
        layout.addWidget(self.value)
        layout.addWidget(self.unit)
        self.setMaximumHeight(76)


class StatusPill(QFrame):
    COLORS = {
        "ONLINE": "#26a269",
        "READY": "#26a269",
        "OFFLINE": "#f85149",
        "FAULT": "#f85149",
        "NOT CONFIGURED": "#d29922",
        "LOCAL": "#2f81f7",
        "LOCAL TEST": "#2f81f7",
        "BYPASSED": "#d29922",
    }

    def __init__(self, name: str, state: str) -> None:
        super().__init__()
        self.setObjectName("statusbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.name = QLabel(name)
        self.name.setStyleSheet("color:#7f91a3; font-size:10px; font-weight:600;")
        self.state = QLabel()
        self.state.setStyleSheet("font-size:10px; font-weight:700;")
        layout.addWidget(self.dot)
        layout.addWidget(self.name)
        layout.addWidget(self.state)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        color = self.COLORS.get(state, "#8b9aab")
        self.dot.setStyleSheet(f"background:{color}; border-radius:4px;")
        self.state.setText(state)
        self.state.setStyleSheet(f"color:{color}; font-size:10px; font-weight:700;")


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: dict,
        pipeline: VisionPipeline,
        evidence: EvidenceWriter | None = None,
        project_root: Path | None = None,
    ):
        super().__init__()
        self.config = config
        self.pipeline = pipeline
        self.evidence = evidence
        self.local_test_mode = bool(
            config.get("classification", {}).get("local_test_mode", False)
        )
        self.camera: OpenCVCamera | None = None
        self.frames: deque[np.ndarray] = deque(
            maxlen=int(config["acquisition"].get("burst_frames", 15))
        )
        self.previous_label: np.ndarray | None = None
        self.focus_overlay_enabled = False
        self.live_package: PackageDetection | None = None
        self._live_detection_counter = 0
        self._live_detection_misses = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._inspection_started = 0.0
        self.total_count = 0
        self.qr_success_count = 0
        self.pass_count = 0
        self.reject_count = 0
        self.review_count = 0
        self.conveyor_state = "UNKNOWN"
        self.conveyor_speed = 0
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.scene_manifest: SceneManifest | None = None
        self.scene_manifest_error: str | None = None
        manifest_relative = config.get("digital_twin", {}).get(
            "manifest_path", "assets/digital_twin/scene_manifest.json"
        )
        try:
            self.scene_manifest = load_scene_manifest(
                self.project_root / manifest_relative, self.project_root
            )
        except (OSError, TypeError, ValueError) as exc:
            self.scene_manifest_error = str(exc)
        self.setWindowTitle(f"{config['station']['name']} · Machine Vision v{__version__} · ESP32 UDP")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 12, 14, 12)
        main.setSpacing(10)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        header = QHBoxLayout(topbar)
        header.setContentsMargins(10, 8, 10, 8)
        brand = QLabel("MV")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(42, 42)
        brand.setStyleSheet(
            "background:#2f81e5; color:white; border-radius:10px; font-size:15px; font-weight:800;"
        )
        header.addWidget(brand)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("MV-01  /  PARCEL INSPECTION CELL")
        title.setObjectName("title")
        subtitle = QLabel("CAMERA 2K  •  QR  •  LOGO  •  PACKAGE DAMAGE  •  SORTING")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("color:#b8c5d1; font-weight:600;")
        header.addWidget(self.clock_label)
        self.mode_label = QLabel("VISION MANUAL")
        self.mode_label.setStyleSheet(
            "background:#142f49; color:#73b6fa; border:1px solid #285078;"
            "border-radius:10px; padding:6px 11px; font-weight:700;"
        )
        header.addWidget(self.mode_label)
        main.addWidget(topbar)
        self._update_clock()

        statuses = QHBoxLayout()
        statuses.setSpacing(8)
        self.camera_status = StatusPill("CAMERA", "OFFLINE")
        self.vision_status = StatusPill("VISION", "READY")
        self.controller_status = StatusPill("CONTROLLER", "NOT CONFIGURED")
        self.data_status = StatusPill(
            "DATA", "LOCAL TEST" if self.local_test_mode else "LOCAL"
        )
        self.remote_status = StatusPill(
            "SUPABASE", "BYPASSED" if self.local_test_mode else "NOT CONFIGURED"
        )
        for status in (
            self.camera_status,
            self.vision_status,
            self.controller_status,
            self.data_status,
            self.remote_status,
        ):
            statuses.addWidget(status)
        statuses.addStretch()
        main.addLayout(statuses)

        kpis = QHBoxLayout()
        kpis.setSpacing(8)
        self.throughput_metric = MetricCard(
            "TOTAL PROCESSED", "0", "kiện trong phiên", "#3b92f6"
        )
        self.success_metric = MetricCard("SCAN SUCCESS", "—", "%", "#6aa9df")
        self.pass_metric = MetricCard("PASS", "0", "kiện trong ca", "#26a269")
        self.reject_metric = MetricCard("REJECT", "0", "kiện lỗi", "#f85149")
        self.cycle_metric = MetricCard("CYCLE TIME", "—", "ms / kiện", "#d29922")
        for metric in (
            self.throughput_metric,
            self.success_metric,
            self.pass_metric,
            self.reject_metric,
            self.cycle_metric,
        ):
            kpis.addWidget(metric, 1)
        main.addLayout(kpis)

        operator_page = QWidget()
        operator_layout = QVBoxLayout(operator_page)
        operator_layout.setContentsMargins(0, 0, 0, 0)
        operator_layout.setSpacing(8)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        camera_panel = QFrame()
        camera_panel.setObjectName("panel")
        camera_layout = QVBoxLayout(camera_panel)
        camera_layout.setContentsMargins(10, 10, 10, 10)
        camera_header = QHBoxLayout()
        self.camera_title = QLabel("LIVE VISION / PHÁT HIỆN KIỆN HÀNG")
        self.camera_title.setObjectName("sectionTitle")
        self.frame_state = QLabel("WAITING")
        self.frame_state.setStyleSheet("color:#8c9bab; font-weight:700;")
        camera_header.addWidget(self.camera_title)
        camera_header.addStretch()
        self.camera_view_group = QButtonGroup(self)
        self.camera_view_group.setExclusive(True)
        self.live_view_button = QPushButton("LIVE")
        self.live_view_button.setObjectName("viewPreset")
        self.live_view_button.setCheckable(True)
        self.live_view_button.setChecked(True)
        self.live_view_button.clicked.connect(self._show_live_view)
        self.snapshot_view_button = QPushButton("ẢNH KIỂM TRA")
        self.snapshot_view_button.setObjectName("viewPreset")
        self.snapshot_view_button.setCheckable(True)
        self.snapshot_view_button.setEnabled(False)
        self.snapshot_view_button.clicked.connect(self._show_snapshot_view)
        self.camera_view_group.addButton(self.live_view_button)
        self.camera_view_group.addButton(self.snapshot_view_button)
        camera_header.addWidget(self.live_view_button)
        camera_header.addWidget(self.snapshot_view_button)
        camera_header.addWidget(self.frame_state)
        camera_layout.addLayout(camera_header)
        self.video_stack = QStackedWidget()
        self.video = VideoCanvas()
        self.snapshot_video = VideoCanvas()
        self.snapshot_video.setText("CHƯA CÓ ẢNH KIỂM TRA")
        self.video_stack.addWidget(self.video)
        self.video_stack.addWidget(self.snapshot_video)
        camera_layout.addWidget(self.video_stack, 1)

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(5)
        self.connect_button = QPushButton("KẾT NỐI CAMERA")
        self.connect_button.setObjectName("secondary")
        self.connect_button.clicked.connect(self.toggle_camera)
        self.inspect_button = QPushButton("KIỂM TRA KIỆN")
        self.inspect_button.setEnabled(False)
        self.inspect_button.clicked.connect(self.inspect)
        self.bench_check = QCheckBox("BENCH 15–30 CM")
        self.bench_check.setToolTip(
            "Chế độ thử tạm khi camera đặt trên bàn/sàn, kiện đứng yên ở 15–30 cm. "
            "Tắt chế độ này khi lắp camera lên băng tải."
        )
        self.bench_check.setChecked(self.pipeline.bench_mode)
        self.bench_check.toggled.connect(self._set_bench_mode)
        self.background_button = QPushButton("CHỤP NỀN TRỐNG")
        self.background_button.setObjectName("secondary")
        self.background_button.setEnabled(False)
        self.background_button.setToolTip(
            "Bỏ kiện khỏi khung hình rồi chụp bối cảnh trống làm mốc kiểm tra móp, méo, thủng."
        )
        self.background_button.clicked.connect(self._capture_bench_background)
        self.logo_calibration_button = QPushButton("LẤY MẪU LOGO")
        self.logo_calibration_button.setObjectName("secondary")
        self.logo_calibration_button.setEnabled(False)
        self.logo_calibration_button.setToolTip(
            "Chụp nhãn thực tế, kéo chọn logo và lưu template nhận diện mới."
        )
        self.logo_calibration_button.clicked.connect(self._open_logo_calibration)
        self.focus_check = QCheckBox("Focus peaking")
        self.focus_check.toggled.connect(self._set_focus_overlay)
        controls.addWidget(self.connect_button, 0, 0)
        controls.addWidget(self.inspect_button, 0, 1)
        controls.addWidget(self.logo_calibration_button, 0, 2)
        controls.addWidget(self.bench_check, 1, 0)
        controls.addWidget(self.background_button, 1, 1)
        controls.addWidget(self.focus_check, 1, 2)
        controls.setColumnStretch(3, 1)
        camera_layout.addLayout(controls)
        body_layout.addWidget(camera_panel, 7)

        right_panel = QWidget()
        sidebar = QVBoxLayout(right_panel)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(8)
        twin_panel = QFrame()
        twin_panel.setObjectName("panel")
        twin_layout = QVBoxLayout(twin_panel)
        twin_header = QHBoxLayout()
        twin_title = QLabel("DIGITAL TWIN 3D / FULL SYSTEM")
        twin_title.setObjectName("sectionTitle")
        self.twin_sync = QLabel("LOCAL MODEL")
        self.twin_sync.setStyleSheet("color:#d29922; font-weight:700; font-size:10px;")
        twin_header.addWidget(twin_title)
        twin_header.addStretch()
        twin_header.addWidget(self.twin_sync)
        twin_layout.addLayout(twin_header)
        self.digital_twin = DigitalTwinWidget()
        twin_layout.addWidget(self.digital_twin)
        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.focus_metric = MetricCard("LAPLACIAN", unit="độ nét", accent="#3b92f6")
        self.tenengrad_metric = MetricCard("TENENGRAD", unit="gradient", accent="#3b92f6")
        self.motion_metric = MetricCard("MOTION", unit="pixel delta", accent="#d29922")
        self.quality_metric = MetricCard(
            "QUALITY GATE", unit="điều kiện chụp", accent="#26a269"
        )
        metrics.addWidget(self.focus_metric, 0, 0)
        metrics.addWidget(self.tenengrad_metric, 0, 1)
        metrics.addWidget(self.motion_metric, 1, 0)
        metrics.addWidget(self.quality_metric, 1, 1)
        sidebar.addLayout(metrics)

        result_panel = QFrame()
        result_panel.setObjectName("panel")
        result_layout = QVBoxLayout(result_panel)
        result_title = QLabel("CURRENT PARCEL / KẾT QUẢ GẦN NHẤT")
        result_title.setObjectName("sectionTitle")
        result_layout.addWidget(result_title)
        self.decision_label = QLabel("WAITING")
        self.decision_label.setStyleSheet(
            "font-size:23px; font-weight:800; color:#8296b0; padding:2px 0 5px 0;"
        )
        self.waybill_label = QLabel("—")
        self.qr_payload_label = QLabel("—")
        self.logo_label = QLabel("—")
        self.damage_label = QLabel("—")
        self.destination_label = QLabel("—")
        self.background_status_label = QLabel("—")
        self.reason_label = QLabel("Chưa có sản phẩm")
        self.reason_label.setWordWrap(True)
        self.reason_label.setObjectName("reasonBox")
        result_layout.addWidget(self.decision_label)
        result_grid = QGridLayout()
        result_grid.setHorizontalSpacing(10)
        result_grid.setVerticalSpacing(6)
        result_fields = (
            ("MÃ VẬN ĐƠN", self.waybill_label),
            ("QR PAYLOAD", self.qr_payload_label),
            ("LOGO", self.logo_label),
            ("TÌNH TRẠNG KIỆN", self.damage_label),
            (
                "KẾT QUẢ LOCAL" if self.local_test_mode else "RỔ ĐÍCH",
                self.destination_label,
            ),
            ("NỀN DAMAGE", self.background_status_label),
        )
        for row, (name, value) in enumerate(result_fields):
            field_name = QLabel(name)
            field_name.setObjectName("fieldName")
            value.setObjectName("fieldValue")
            value.setWordWrap(True)
            result_grid.addWidget(field_name, row, 0)
            result_grid.addWidget(value, row, 1)
        result_grid.setColumnStretch(1, 1)
        result_layout.addLayout(result_grid)
        result_layout.addWidget(self.reason_label)
        sidebar.addWidget(result_panel)
        body_layout.addWidget(right_panel, 3)
        operator_layout.addWidget(body, 1)

        tabs = QTabWidget()
        self.history = QTableWidget(0, 6)
        self.history.setHorizontalHeaderLabels(
            [
                "Thời gian",
                "Mã vận đơn",
                "QR",
                "Quyết định",
                "Kết quả local" if self.local_test_mode else "Rổ",
                "Lý do",
            ]
        )
        self.history.horizontalHeader().setStretchLastSection(True)
        self.history.verticalHeader().setVisible(False)
        self.history.verticalHeader().setDefaultSectionSize(27)
        self.history.setShowGrid(False)
        self.history.setAlternatingRowColors(True)
        self.history.setMaximumHeight(165)
        self.alarms = QTableWidget(1, 3)
        self.alarms.setHorizontalHeaderLabels(["Mức độ", "Nguồn", "Thông báo"])
        self.alarms.horizontalHeader().setStretchLastSection(True)
        self.alarms.verticalHeader().setVisible(False)
        self.alarms.verticalHeader().setDefaultSectionSize(27)
        self.alarms.setShowGrid(False)
        self.alarms.setItem(0, 0, QTableWidgetItem("WARNING"))
        self.alarms.setItem(0, 1, QTableWidgetItem("REMOTE"))
        self.alarms.setItem(0, 2, QTableWidgetItem("Kênh giám sát từ xa chưa được cấu hình"))
        tabs.addTab(self.history, "EVENT LOG")
        tabs.addTab(self.alarms, "ALARMS (1)")
        tabs.setMaximumHeight(145)
        operator_layout.addWidget(tabs)

        twin_page = QWidget()
        twin_page_layout = QVBoxLayout(twin_page)
        twin_page_layout.setContentsMargins(0, 0, 0, 0)
        twin_page_layout.setSpacing(8)

        twin_command_bar = QFrame()
        twin_command_bar.setObjectName("subpanel")
        command_layout = QHBoxLayout(twin_command_bar)
        command_layout.setContentsMargins(10, 7, 10, 7)
        cell_label = QLabel("CELL MV-01")
        cell_label.setObjectName("sectionTitle")
        command_layout.addWidget(cell_label)
        command_layout.addSpacing(10)
        command_layout.addWidget(StatusPill("CELL", "READY"))
        command_layout.addWidget(StatusPill("SYNC", "LOCAL"))
        command_layout.addStretch()
        frame_label = QLabel("FRAME  •  WORLD / Y-UP / METERS")
        frame_label.setStyleSheet("color:#71879a; font-size:10px; font-weight:600;")
        command_layout.addWidget(frame_label)
        twin_page_layout.addWidget(twin_command_bar)

        engineering_split = QSplitter(Qt.Orientation.Horizontal)
        engineering_split.setChildrenCollapsible(False)
        engineering_split.addWidget(self._build_scene_browser())
        engineering_split.addWidget(twin_panel)
        engineering_split.addWidget(self._build_twin_controls())
        engineering_split.setStretchFactor(0, 0)
        engineering_split.setStretchFactor(1, 1)
        engineering_split.setStretchFactor(2, 0)
        engineering_split.setSizes([215, 800, 290])
        twin_page_layout.addWidget(engineering_split, 1)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.addTab(operator_page, "VẬN HÀNH")
        self.workspace_tabs.addTab(twin_page, "DIGITAL TWIN 3D")
        conveyor_page = QWidget()
        conveyor_layout = QVBoxLayout(conveyor_page)
        conveyor_layout.setContentsMargins(18, 18, 18, 18)
        conveyor_intro = QLabel(
            "ĐIỀU KHIỂN BĂNG TẢI THỬ NGHIỆM · Lệnh gửi thủ công tới ESP32/W5500. "
            "Không có điều khiển phân loại tự động hoặc cảm biến tốc độ thực."
        )
        conveyor_intro.setWordWrap(True)
        conveyor_intro.setObjectName("sectionTitle")
        conveyor_layout.addWidget(conveyor_intro)
        panel_row = QHBoxLayout()
        self.conveyor_panel = ConveyorPanel(self.config.get("controller", {}))
        self.conveyor_panel.setMaximumWidth(650)
        self.conveyor_panel.state_changed.connect(self._on_conveyor_state)
        self.conveyor_panel.connection_changed.connect(self._on_controller_connection)
        panel_row.addWidget(self.conveyor_panel)
        panel_row.addStretch()
        conveyor_layout.addLayout(panel_row)
        safety = QLabel(
            "AN TOÀN: STOP trong GUI là gói UDP, không phải dừng khẩn. "
            "Cần công tắc ngắt nguồn motor/E-stop phần cứng và giám sát trực tiếp khi thử. "
            "Mất ACK nghĩa là trạng thái thực không xác định."
        )
        safety.setWordWrap(True)
        safety.setStyleSheet("color:#e0ad47; font-weight:600;")
        conveyor_layout.addWidget(safety)
        conveyor_layout.addStretch()
        self.workspace_tabs.addTab(conveyor_page, "BĂNG TẢI / ESP32")
        main.addWidget(self.workspace_tabs, 1)
        self.setCentralWidget(root)
        self._set_bench_mode(self.pipeline.bench_mode)

    def _build_scene_browser(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(190)
        panel.setMaximumWidth(245)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        title = QLabel("SCENE EXPLORER")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        subtitle = QLabel("CẤU TRÚC THIẾT BỊ")
        subtitle.setStyleSheet("color:#657b8e; font-size:9px; font-weight:600;")
        layout.addWidget(subtitle)

        self.scene_tree = QTreeWidget()
        self.scene_tree.setHeaderHidden(True)
        self.scene_tree.setIndentation(15)
        self.scene_tree.setAnimated(True)
        self.scene_tree.setAlternatingRowColors(True)
        cell = QTreeWidgetItem(["▣  CELL MV-01"])
        conveyor = QTreeWidgetItem(["▰  Main conveyor"])
        vision = QTreeWidgetItem(["⌁  Vision gantry"])
        vision.addChildren(
            [QTreeWidgetItem(["◉  Camera 2K"]), QTreeWidgetItem(["◇  Sensor S1"])]
        )
        robot = QTreeWidgetItem(["⌬  Robot 6-DOF"])
        bins = QTreeWidgetItem(["▱  Sorting bins"])
        bins.addChildren(
            [QTreeWidgetItem(["Pass"]), QTreeWidgetItem(["Defect"]), QTreeWidgetItem(["Review"])]
        )
        cell.addChildren([conveyor, vision, robot, bins])
        self.scene_tree.addTopLevelItem(cell)
        cell.setExpanded(True)
        vision.setExpanded(True)
        bins.setExpanded(True)
        self.scene_tree.currentItemChanged.connect(self._scene_item_selected)
        self.scene_tree.setCurrentItem(cell)
        layout.addWidget(self.scene_tree, 1)

        layer_title = QLabel("LAYERS")
        layer_title.setObjectName("sectionTitle")
        layout.addWidget(layer_title)
        self.layer_checks: dict[str, QCheckBox] = {}
        for layer, text in (
            ("equipment", "Thiết bị"),
            ("vision_zones", "Vision zones"),
            ("telemetry_labels", "Telemetry labels"),
        ):
            option = QCheckBox(text)
            option.setChecked(True)
            option.setMinimumHeight(25)
            option.toggled.connect(
                lambda visible, name=layer: self.digital_twin.set_layer_visible(name, visible)
            )
            layout.addWidget(option)
            self.layer_checks[layer] = option
        return panel

    def _scene_item_selected(self, current: QTreeWidgetItem | None, _previous) -> None:
        if current is None:
            return
        text = current.text(0).lower()
        if "robot" in text:
            self._set_twin_view("robot")
            if hasattr(self, "inspector_tabs"):
                self.inspector_tabs.setCurrentIndex(1)
        elif "camera" in text or "vision" in text:
            self._set_twin_view("front")
            if hasattr(self, "inspector_tabs"):
                self.inspector_tabs.setCurrentIndex(0)
        elif "conveyor" in text:
            self._set_twin_view("top")
            if hasattr(self, "inspector_tabs"):
                self.inspector_tabs.setCurrentIndex(0)
        elif "cell" in text or "bin" in text:
            self._set_twin_view("isometric")

    def _set_twin_view(self, preset: str) -> None:
        self.digital_twin.set_view(preset)
        if hasattr(self, "view_buttons") and preset in self.view_buttons:
            self.view_buttons[preset].setChecked(True)

    def _build_twin_controls(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(290)
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("INSPECTOR / TELEMETRY")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setObjectName("inspectorTabs")
        self.inspector_tabs.setDocumentMode(True)
        self.inspector_tabs.tabBar().setExpanding(True)
        self.inspector_tabs.tabBar().setUsesScrollButtons(False)

        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(8, 10, 8, 8)
        overview_layout.setSpacing(8)

        view_title = QLabel("CAMERA VIEW PRESETS")
        view_title.setObjectName("sectionTitle")
        overview_layout.addWidget(view_title)

        view_grid = QGridLayout()
        view_grid.setHorizontalSpacing(7)
        view_grid.setVerticalSpacing(7)
        self.view_button_group = QButtonGroup(self)
        self.view_button_group.setExclusive(True)
        self.view_buttons: dict[str, QPushButton] = {}
        for index, (text, preset) in enumerate(
            (("ISOMETRIC", "isometric"), ("TOP", "top"), ("FRONT", "front"), ("ROBOT", "robot"))
        ):
            button = QPushButton(text)
            button.setObjectName("viewPreset")
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.setChecked(preset == "isometric")
            button.clicked.connect(
                lambda _checked=False, name=preset: self._set_twin_view(name)
            )
            self.view_button_group.addButton(button)
            self.view_buttons[preset] = button
            view_grid.addWidget(button, index // 2, index % 2)
        overview_layout.addLayout(view_grid)

        hint = QLabel(
            "Chuột trái: xoay camera\n"
            "Chuột phải: dịch chuyển\n"
            "Con lăn: phóng to / thu nhỏ  •  Double-click: reset"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#7f91a3; font-size:10px;")
        overview_layout.addWidget(hint)

        state_title = QLabel("TRẠNG THÁI HỆ THỐNG")
        state_title.setObjectName("sectionTitle")
        overview_layout.addWidget(state_title)
        self.twin_stage_value = QLabel("Stage: IDLE")
        self.twin_conveyor_value = QLabel("Conveyor: UNKNOWN")
        self.twin_robot_value = QLabel("Robot: READY")
        for label in (
            self.twin_stage_value,
            self.twin_conveyor_value,
            self.twin_robot_value,
        ):
            label.setStyleSheet("background:#0d141d; padding:6px; color:#aebdca;")
            label.setMinimumHeight(30)
            overview_layout.addWidget(label)
        overview_layout.addStretch()

        robot_page = QWidget()
        robot_layout = QVBoxLayout(robot_page)
        robot_layout.setContentsMargins(8, 10, 8, 8)
        robot_layout.setSpacing(8)

        joint_title = QLabel("ROBOT 6 BẬC TỰ DO")
        joint_title.setObjectName("sectionTitle")
        robot_layout.addWidget(joint_title)
        robot_hint = QLabel("Điều khiển mô phỏng góc khớp • đơn vị độ")
        robot_hint.setStyleSheet("color:#7f91a3; font-size:10px;")
        robot_layout.addWidget(robot_hint)
        limits = ((-180, 180), (-90, 90), (-130, 130), (-180, 180), (-120, 120), (-360, 360))
        self.joint_value_labels: list[QLabel] = []
        for joint, (minimum, maximum) in enumerate(limits):
            row = QHBoxLayout()
            row.setSpacing(7)
            name = QLabel(f"J{joint + 1}")
            name.setFixedWidth(22)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimumHeight(25)
            slider.setRange(minimum, maximum)
            slider.setValue(self.digital_twin.robot_angles[joint])
            value = QLabel(f"{slider.value()}°")
            value.setFixedWidth(42)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            slider.valueChanged.connect(
                lambda angle, index=joint, output=value: self._set_robot_joint(index, angle, output)
            )
            row.addWidget(name)
            row.addWidget(slider, 1)
            row.addWidget(value)
            robot_layout.addLayout(row)
            self.joint_value_labels.append(value)
        robot_layout.addStretch()

        assets_page = QWidget()
        asset_layout = QVBoxLayout(assets_page)
        asset_layout.setContentsMargins(8, 10, 8, 8)
        asset_layout.setSpacing(8)
        asset_title = QLabel("3D ASSET PIPELINE")
        asset_title.setObjectName("sectionTitle")
        asset_layout.addWidget(asset_title)
        asset_help = QLabel(
            "Mô hình phần mềm tiếp tục hoạt động cho tới khi file GLB được commissioning."
        )
        asset_help.setWordWrap(True)
        asset_help.setStyleSheet("color:#7f91a3; font-size:10px;")
        asset_layout.addWidget(asset_help)
        if self.scene_manifest_error:
            error = QLabel("MANIFEST ERROR")
            error.setObjectName("assetWaiting")
            error.setToolTip(self.scene_manifest_error)
            asset_layout.addWidget(error)
        elif self.scene_manifest is not None:
            for asset in self.scene_manifest.assets:
                ready = asset.is_ready(self.project_root)
                row_panel = QFrame()
                row_panel.setObjectName("subpanel")
                row_layout = QHBoxLayout(row_panel)
                row_layout.setContentsMargins(8, 7, 8, 7)
                name = QLabel(asset.asset_id.upper())
                name.setToolTip(asset.label)
                name.setStyleSheet("color:#aebdca; font-size:10px; font-weight:600;")
                state = QLabel("READY" if ready else "AWAITING GLB")
                state.setObjectName("assetReady" if ready else "assetWaiting")
                row_layout.addWidget(name, 1)
                row_layout.addWidget(state)
                asset_layout.addWidget(row_panel)
        asset_layout.addStretch()

        self.inspector_tabs.addTab(overview_page, "OVERVIEW")
        self.inspector_tabs.addTab(robot_page, "ROBOT")
        self.inspector_tabs.addTab(assets_page, "ASSETS")
        layout.addWidget(self.inspector_tabs, 1)
        return panel

    def _set_robot_joint(self, joint: int, angle: int, output: QLabel) -> None:
        self.digital_twin.set_joint_angle(joint, angle)
        output.setText(f"{angle}°")

    def _set_twin_process(
        self,
        stage: ProcessStage,
        decision: str | None = None,
    ) -> None:
        self.digital_twin.set_process_state(
            stage, decision, self.conveyor_state in {"FWD", "REV"}
        )
        self.digital_twin.set_conveyor_command_state(self.conveyor_state)
        self.twin_stage_value.setText(f"Stage: {stage.value}")
        self.twin_conveyor_value.setText(f"Conveyor cmd: {self.conveyor_state} · PWM {self.conveyor_speed}")

    def _on_conveyor_state(self, state: str, speed: int) -> None:
        self.conveyor_state = state
        self.conveyor_speed = speed
        self._set_twin_process(self.digital_twin.stage, self.digital_twin.decision)

    def _on_controller_connection(self, online: bool) -> None:
        self.controller_status.set_state("ONLINE" if online else "FAULT")

    def toggle_camera(self) -> None:
        if self.camera is not None:
            self.timer.stop()
            self.camera.close()
            self.camera = None
            self.camera_status.set_state("OFFLINE")
            self.frame_state.setText("WAITING")
            self.frame_state.setStyleSheet("color:#8c9bab; font-weight:700;")
            self._set_twin_process(ProcessStage.IDLE)
            self.connect_button.setText("KẾT NỐI CAMERA")
            self.inspect_button.setEnabled(False)
            self.background_button.setEnabled(False)
            self.logo_calibration_button.setEnabled(False)
            self.live_package = None
            return
        try:
            self.camera = OpenCVCamera(self.config["camera"])
        except CameraError as exc:
            QMessageBox.critical(self, "Camera error", str(exc))
            return
        self.camera_status.set_state("ONLINE")
        self.frame_state.setText("LIVE")
        self.frame_state.setStyleSheet("color:#26a269; font-weight:700;")
        self._set_twin_process(ProcessStage.DETECT)
        self.connect_button.setText("NGẮT CAMERA")
        self.inspect_button.setEnabled(True)
        self.background_button.setEnabled(self.pipeline.bench_mode)
        self.logo_calibration_button.setEnabled(True)
        self.timer.start(33)

    def _set_focus_overlay(self, enabled: bool) -> None:
        self.focus_overlay_enabled = enabled

    def _show_live_view(self) -> None:
        self.video_stack.setCurrentWidget(self.video)
        self.live_view_button.setChecked(True)
        self.camera_title.setText("LIVE VISION / PHÁT HIỆN KIỆN HÀNG")

    def _show_snapshot_view(self) -> None:
        if not self.snapshot_view_button.isEnabled():
            self._show_live_view()
            return
        self.video_stack.setCurrentWidget(self.snapshot_video)
        self.snapshot_view_button.setChecked(True)
        self.camera_title.setText("ẢNH KIỆN TẠI THỜI ĐIỂM KIỂM TRA")

    def _update_damage_reference_status(self) -> None:
        if not hasattr(self, "background_status_label"):
            return
        ready = self.pipeline.damage_reference_ready()
        if ready:
            self.background_status_label.setText("SẴN SÀNG")
            self.background_status_label.setStyleSheet(
                "color:#26a269; font-weight:700;"
            )
        else:
            self.background_status_label.setText("CHƯA CHỤP NỀN")
            self.background_status_label.setStyleSheet(
                "color:#d29922; font-weight:700;"
            )

    def _capture_bench_background(self) -> None:
        if not self.pipeline.bench_mode:
            QMessageBox.information(
                self,
                "Chụp nền trống",
                "Chức năng này chỉ dùng trong chế độ BENCH 15–30 CM.",
            )
            return
        if not self.frames:
            QMessageBox.warning(
                self, "Chụp nền trống", "Camera chưa có hình ảnh để hiệu chuẩn."
            )
            return
        answer = QMessageBox.question(
            self,
            "Xác nhận bối cảnh trống",
            "Hãy lấy kiện hàng ra khỏi khung hình, giữ nguyên camera và ánh sáng.\n\n"
            "Khung hình hiện tại không còn kiện hàng?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path = self.pipeline.capture_bench_background(self.frames[-1])
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi chụp nền", str(exc))
            return
        self.frames.clear()
        self.previous_label = None
        self.live_package = None
        self._update_damage_reference_status()
        QMessageBox.information(
            self,
            "Đã chụp nền trống",
            "Ảnh nền đã được lưu. Bây giờ hãy đặt kiện vào đúng vị trí, "
            f"chờ hình ổn định rồi nhấn KIỂM TRA KIỆN.\n\n{path}",
        )

    def _open_logo_calibration(self) -> None:
        if self.camera is None or not self.frames:
            QMessageBox.warning(
                self,
                "Hiệu chuẩn logo",
                "Hãy kết nối camera và chờ hình ảnh ổn định trước khi lấy mẫu logo.",
            )
            return
        dialog = LogoCalibrationDialog(
            self.pipeline,
            frame_provider=lambda: list(self.frames),
            parent=self,
        )
        if dialog.exec():
            self.logo_label.setText("TEMPLATE MỚI — SẴN SÀNG")
            self.logo_label.setStyleSheet("color:#26a269; font-weight:700;")

    def _set_bench_mode(self, enabled: bool) -> None:
        self.pipeline.set_bench_mode(enabled)
        self.frames.clear()
        self.previous_label = None
        self.live_package = None
        acquisition = self.pipeline.acquisition_settings()
        self.focus_metric.unit.setText(
            f"độ nét • ngưỡng ≥ {float(acquisition.get('min_laplacian', 0)):.1f}"
        )
        self.tenengrad_metric.unit.setText(
            f"gradient • ngưỡng ≥ {float(acquisition.get('min_tenengrad', 0)):.0f}"
        )
        if enabled:
            self.mode_label.setText("BENCH 15–30 CM")
            self.mode_label.setStyleSheet(
                "background:#3a2a0e; color:#f0b84b; border:1px solid #71551f;"
                "border-radius:10px; padding:6px 11px; font-weight:700;"
            )
            self.bench_check.setStyleSheet("color:#f0b84b; font-weight:700;")
        else:
            self.mode_label.setText("VISION MANUAL")
            self.mode_label.setStyleSheet(
                "background:#142f49; color:#73b6fa; border:1px solid #285078;"
                "border-radius:10px; padding:6px 11px; font-weight:700;"
            )
            self.bench_check.setStyleSheet("")
        if hasattr(self, "background_button"):
            self.background_button.setEnabled(enabled and self.camera is not None)
        self._update_damage_reference_status()

    def _next_frame(self) -> None:
        if self.camera is None:
            return
        try:
            frame = self.camera.read()
        except CameraError as exc:
            self.timer.stop()
            QMessageBox.critical(self, "Camera error", str(exc))
            return
        self.frames.append(frame.copy())
        label = crop_fraction(frame, self.config["label"]["roi"])
        metrics = assess_focus(label, self.previous_label)
        self.previous_label = label
        good = is_acceptable(metrics, self.pipeline.acquisition_settings())
        self.focus_metric.value.setText(f"{metrics.laplacian:.0f}")
        self.tenengrad_metric.value.setText(f"{metrics.tenengrad:.0f}")
        self.motion_metric.value.setText(f"{metrics.motion:.1f}")
        self.quality_metric.value.setText("READY" if good else "HOLD")
        self.quality_metric.value.setStyleSheet(
            "color:#26a269;" if good else "color:#d29922;"
        )
        self._live_detection_counter += 1
        interval = max(
            1, int(self.config.get("package_detection", {}).get("live_interval_frames", 10))
        )
        if self._live_detection_counter % interval == 1:
            detected = self.pipeline.detect_package_fast(frame)
            if detected is not None:
                self.live_package = detected
                self._live_detection_misses = 0
            else:
                self._live_detection_misses += 1
                if self._live_detection_misses >= 3:
                    self.live_package = None

        # Focus feedback is useful on the printed label, not on carton creases/floor edges.
        focus_roi = self.live_package.label_bbox if self.live_package is not None else None
        if focus_roi is None:
            fx, fy, fw, fh = self.config["label"]["roi"]
            focus_roi = (
                int(fx * frame.shape[1]),
                int(fy * frame.shape[0]),
                int(fw * frame.shape[1]),
                int(fh * frame.shape[0]),
            )
        display = (
            focus_peaking(frame, roi=focus_roi)
            if self.focus_overlay_enabled
            else frame.copy()
        )
        if self.live_package is not None:
            display = self.pipeline.draw_package_detection(display, self.live_package)
        self.video.show_frame(display)

    def inspect(self) -> None:
        if not self.frames:
            return
        self._inspection_started = perf_counter()
        self.frame_state.setText("INSPECTING")
        self.frame_state.setStyleSheet("color:#2f81f7; font-weight:700;")
        self._set_twin_process(ProcessStage.VISION)
        try:
            result = self.pipeline.inspect(list(self.frames))
        except FrameQualityError as exc:
            self.frame_state.setText("QUALITY HOLD")
            self.frame_state.setStyleSheet("color:#d29922; font-weight:700;")
            self._set_twin_process(ProcessStage.VISION)
            QMessageBox.warning(self, "Quality gate", str(exc))
            return
        except Exception as exc:  # show adapter/runtime errors to the operator
            self.vision_status.set_state("FAULT")
            self.frame_state.setText("FAULT")
            self.frame_state.setStyleSheet("color:#f85149; font-weight:700;")
            QMessageBox.critical(self, "Inspection error", str(exc))
            return
        if self.evidence is not None:
            try:
                self.evidence.save(result)
            except Exception as exc:
                QMessageBox.warning(self, "Audit storage warning", str(exc))
        self._show_result(result)

    def _show_result(self, result: InspectionResult) -> None:
        classification = result.classification
        colors = {
            Decision.PASS: "#26a269",
            Decision.REJECT: "#f85149",
            Decision.MANUAL_REVIEW: "#d29922",
        }
        backgrounds = {
            Decision.PASS: "rgba(38,162,105,35)",
            Decision.REJECT: "rgba(248,81,73,35)",
            Decision.MANUAL_REVIEW: "rgba(210,153,34,35)",
        }
        decision_text = classification.decision.value
        if self.local_test_mode:
            decision_text = {
                Decision.PASS: "LOCAL PASS",
                Decision.REJECT: "LOCAL FAIL",
                Decision.MANUAL_REVIEW: "LOCAL REVIEW",
            }[classification.decision]
        self.decision_label.setText(decision_text)
        self.decision_label.setStyleSheet(
            f"font-size:23px; font-weight:800; color:{colors[classification.decision]};"
            f"background:{backgrounds[classification.decision]}; border-radius:6px;"
            "padding:6px 9px;"
        )
        self.waybill_label.setText(classification.parcel.waybill_code or "—")
        self.qr_payload_label.setText(
            classification.parcel.qr_text or "KHÔNG ĐỌC ĐƯỢC"
        )
        logo = classification.parcel.logo
        logo_text = "CHƯA HIỆU CHUẨN"
        if logo and logo.calibrated:
            logo_text = "OK" if logo.present else "KHÔNG KHỚP"
            logo_text += f" ({logo.score:.2f})"
        self.logo_label.setText(logo_text)
        damage = classification.parcel.damage
        damage_text = "CHƯA HIỆU CHUẨN"
        if damage and damage.calibrated:
            if damage.damaged is None:
                damage_text = "KHÔNG TÌM THẤY KIỆN"
            elif damage.damaged:
                names = {
                    "deformation": "MÓP / MÉO",
                    "dent_or_edge_tear": "MÓP / RÁCH CẠNH",
                    "irregular_outline": "BIẾN DẠNG",
                    "hole_or_puncture": "THỦNG LỖ",
                }
                translated = [names.get(item, item.upper()) for item in damage.damage_types]
                damage_text = "LỖI — " + ", ".join(translated)
            else:
                damage_text = "BÌNH THƯỜNG"
        self.damage_label.setText(damage_text)
        self.destination_label.setText(classification.destination_bin)
        self.reason_label.setText(classification.reason)
        snapshot = result.debug_images.get("damage_overlay", result.original_frame)
        self.snapshot_video.show_frame(snapshot)
        self.snapshot_view_button.setEnabled(True)
        self._show_snapshot_view()

        elapsed_ms = max(0.0, (perf_counter() - self._inspection_started) * 1000)
        self.total_count += 1
        if classification.decision == Decision.PASS:
            self.pass_count += 1
        elif classification.decision == Decision.REJECT:
            self.reject_count += 1
        else:
            self.review_count += 1
        qr_ok = bool(classification.parcel.qr_text)
        if qr_ok:
            self.qr_success_count += 1
        self.throughput_metric.value.setText(str(self.total_count))
        self.success_metric.value.setText(f"{self.qr_success_count / self.total_count * 100:.1f}")
        self.pass_metric.value.setText(str(self.pass_count))
        self.reject_metric.value.setText(str(self.reject_count))
        self.cycle_metric.value.setText(f"{elapsed_ms:.0f}")
        self.frame_state.setText(classification.decision.value)
        self.frame_state.setStyleSheet(
            f"color:{colors[classification.decision]}; font-weight:700;"
        )
        self._set_twin_process(
            ProcessStage.COMPLETE,
            decision=classification.decision.value,
        )

        self.history.insertRow(0)
        values = (
            datetime.now().strftime("%H:%M:%S"),
            classification.parcel.waybill_code or "—",
            "OK" if qr_ok else "FAIL",
            classification.decision.value,
            classification.destination_bin,
            classification.reason,
        )
        for column, value in enumerate(values):
            self.history.setItem(0, column, QTableWidgetItem(value))

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%d/%m/%Y   %H:%M:%S"))

    def closeEvent(self, event) -> None:
        stop_error = self.conveyor_panel.shutdown()
        if stop_error:
            response = QMessageBox.warning(
                self, "Chưa xác nhận dừng băng tải",
                "ESP32 chưa ACK lệnh STOP. Hãy ngắt nguồn motor bằng phần cứng "
                "và kiểm tra tại chỗ. Chỉ chọn Close khi đã xác minh motor dừng "
                f"và nguồn động lực bị ngắt.\n\n{stop_error}",
                QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if response != QMessageBox.StandardButton.Close:
                event.ignore()
                return
        if self.camera is not None:
            self.camera.close()
        event.accept()
