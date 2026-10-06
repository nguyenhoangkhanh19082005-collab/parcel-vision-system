from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from machine_vision.services.pipeline import FrameQualityError, VisionPipeline


class LogoSelectionCanvas(QWidget):
    selection_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(620, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._image: np.ndarray | None = None
        self._pixmap: QPixmap | None = None
        self._display_rect = QRectF()
        self._start: QPointF | None = None
        self._end: QPointF | None = None
        self._dragging = False

    def set_image(self, image: np.ndarray) -> None:
        self._image = image.copy()
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        qimage = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        self._pixmap = QPixmap.fromImage(qimage)
        self.clear_selection()

    def clear_selection(self) -> None:
        self._start = None
        self._end = None
        self._dragging = False
        self.update()
        self.selection_changed.emit()

    def _clamp(self, point: QPointF) -> QPointF:
        return QPointF(
            max(self._display_rect.left(), min(point.x(), self._display_rect.right())),
            max(self._display_rect.top(), min(point.y(), self._display_rect.bottom())),
        )

    def selection_pixels(self) -> tuple[int, int, int, int] | None:
        if self._image is None or self._start is None or self._end is None:
            return None
        selected = QRectF(self._start, self._end).normalized().intersected(
            self._display_rect
        )
        if selected.width() < 4 or selected.height() < 4:
            return None
        image_height, image_width = self._image.shape[:2]
        x = round(
            (selected.left() - self._display_rect.left())
            / self._display_rect.width()
            * image_width
        )
        y = round(
            (selected.top() - self._display_rect.top())
            / self._display_rect.height()
            * image_height
        )
        width = round(selected.width() / self._display_rect.width() * image_width)
        height = round(selected.height() / self._display_rect.height() * image_height)
        return x, y, width, height

    def selected_image(self) -> np.ndarray | None:
        selection = self.selection_pixels()
        if self._image is None or selection is None:
            return None
        x, y, width, height = selection
        return self._image[y : y + height, x : x + width].copy()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05090d"))
        if self._pixmap is None:
            painter.setPen(QColor("#66798a"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CHƯA CÓ ẢNH NHÃN")
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = (self.width() - scaled.width()) / 2
        top = (self.height() - scaled.height()) / 2
        self._display_rect = QRectF(left, top, scaled.width(), scaled.height())
        painter.drawPixmap(self._display_rect.toRect(), scaled)
        painter.setPen(QPen(QColor("#31495d"), 1))
        painter.drawRect(self._display_rect)
        if self._start is not None and self._end is not None:
            selected = QRectF(self._start, self._end).normalized().intersected(
                self._display_rect
            )
            painter.fillRect(selected, QColor(47, 129, 247, 36))
            painter.setPen(QPen(QColor("#55b6ff"), 3))
            painter.drawRect(selected)
            caption = "LOGO TEMPLATE"
            caption_rect = QRectF(
                selected.left(), max(self._display_rect.top(), selected.top() - 24), 130, 22
            )
            painter.fillRect(caption_rect, QColor("#123b62"))
            painter.setPen(QColor("#dff2ff"))
            painter.drawText(
                caption_rect.adjusted(6, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter,
                caption,
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._pixmap is not None
            and self._display_rect.contains(event.position())
        ):
            self._start = self._clamp(event.position())
            self._end = self._start
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._dragging:
            self._end = self._clamp(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._end = self._clamp(event.position())
            self._dragging = False
            self.update()
            self.selection_changed.emit()


class LogoCalibrationDialog(QDialog):
    def __init__(
        self,
        pipeline: VisionPipeline,
        frame_provider: Callable[[], list[np.ndarray]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.frame_provider = frame_provider
        self.label_image: np.ndarray | None = None
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.setWindowTitle("Hiệu chuẩn logo từ kiện hàng thực tế")
        self.resize(1080, 780)
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("LẤY MẪU LOGO THỰC TẾ")
        title.setObjectName("title")
        layout.addWidget(title)
        help_text = QLabel(
            "1. Đặt kiện đứng yên và nhìn rõ QR  •  2. Nhấn CHỤP ẢNH NHÃN  •  "
            "3. Kéo chuột ôm sát biểu tượng + chữ logo  •  4. Lưu template"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color:#8fa4b6; padding:4px 0 6px 0;")
        layout.addWidget(help_text)

        content = QHBoxLayout()
        content.setSpacing(10)
        self.canvas = LogoSelectionCanvas()
        self.canvas.selection_changed.connect(self._update_preview)
        content.addWidget(self.canvas, 1)

        side = QFrame()
        side.setObjectName("panel")
        side.setFixedWidth(285)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(9)
        preview_title = QLabel("PREVIEW TEMPLATE")
        preview_title.setObjectName("sectionTitle")
        side_layout.addWidget(preview_title)
        self.preview = QLabel("KÉO CHUỘT ĐỂ CHỌN LOGO")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(150)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            "background:#05090d; border:1px solid #263542; color:#607283;"
        )
        side_layout.addWidget(self.preview)
        self.selection_info = QLabel("Vùng chọn: —")
        self.selection_info.setWordWrap(True)
        self.selection_info.setStyleSheet("color:#9eb0bf;")
        side_layout.addWidget(self.selection_info)
        rules = QLabel(
            "Chỉ chọn logo Shopee XPRESS.\n"
            "Không lấy mã vạch, QR, địa chỉ hoặc đường kẻ của nhãn.\n"
            "Logo nên rộng ít nhất 80 px và rõ nét."
        )
        rules.setWordWrap(True)
        rules.setObjectName("reasonBox")
        side_layout.addWidget(rules)
        side_layout.addStretch()
        self.status = QLabel("Đang chờ ảnh từ camera…")
        self.status.setWordWrap(True)
        self.status.setObjectName("reasonBox")
        side_layout.addWidget(self.status)
        content.addWidget(side)
        layout.addLayout(content, 1)

        actions = QHBoxLayout()
        self.capture_button = QPushButton("CHỤP ẢNH NHÃN")
        self.capture_button.clicked.connect(self.capture)
        clear_button = QPushButton("CHỌN LẠI")
        clear_button.setObjectName("secondary")
        clear_button.clicked.connect(self.canvas.clear_selection)
        close_button = QPushButton("ĐÓNG")
        close_button.setObjectName("secondary")
        close_button.clicked.connect(self.reject)
        self.save_button = QPushButton("LƯU TEMPLATE")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_template)
        actions.addWidget(self.capture_button)
        actions.addWidget(clear_button)
        actions.addStretch()
        actions.addWidget(close_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        QTimer.singleShot(0, self.capture)

    def capture(self) -> None:
        frames = self.frame_provider()
        if not frames:
            self.status.setText("Camera chưa có frame. Hãy chờ khoảng 1 giây rồi thử lại.")
            return
        self.capture_button.setEnabled(False)
        self.status.setText("Đang chọn frame tốt nhất và hiệu chỉnh nhãn theo QR…")
        try:
            self.label_image = self.pipeline.capture_logo_calibration(frames)
        except FrameQualityError as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, "Ảnh chưa đạt chất lượng", str(exc))
            return
        except Exception as exc:
            self.status.setText(str(exc))
            QMessageBox.critical(self, "Không thể chụp nhãn", str(exc))
            return
        finally:
            self.capture_button.setEnabled(True)
        self.canvas.set_image(self.label_image)
        height, width = self.label_image.shape[:2]
        self.status.setText(
            f"Đã chụp nhãn chuẩn hóa {width}x{height}. Kéo chuột quanh logo thực tế."
        )

    def _update_preview(self) -> None:
        crop = self.canvas.selected_image()
        selection = self.canvas.selection_pixels()
        self.save_button.setEnabled(crop is not None)
        if crop is None or selection is None:
            self.preview.clear()
            self.preview.setText("KÉO CHUỘT ĐỂ CHỌN LOGO")
            self.selection_info.setText("Vùng chọn: —")
            return
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pixmap)
        x, y, selected_width, selected_height = selection
        self.selection_info.setText(
            f"Vùng chọn: x={x}, y={y}\nKích thước: {selected_width}x{selected_height} px"
        )

    def save_template(self) -> None:
        selection = self.canvas.selection_pixels()
        if self.label_image is None or selection is None:
            QMessageBox.warning(self, "Thiếu vùng logo", "Hãy kéo chuột chọn vùng logo.")
            return
        try:
            result = self.pipeline.calibrate_logo_template(self.label_image, selection)
        except (OSError, RuntimeError, ValueError) as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, "Template chưa hợp lệ", str(exc))
            return
        keypoints = int(result["sift_keypoints"])
        template_path = str(result["template_path"])
        self.status.setText(
            f"Đã lưu và nạp template mới: {keypoints} đặc trưng SIFT."
        )
        QMessageBox.information(
            self,
            "Hiệu chuẩn logo thành công",
            "Template mới đã được nạp ngay vào hệ thống.\n"
            f"SIFT keypoints: {keypoints}\n"
            f"File: {template_path}\n\n"
            "Bạn có thể đóng cửa sổ và nhấn KIỂM TRA KIỆN.",
        )
        self.accept()
