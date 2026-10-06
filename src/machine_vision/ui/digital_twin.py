from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PyQt6.QtWidgets import QWidget

Vec3 = tuple[float, float, float]


class ProcessStage(str, Enum):
    IDLE = "IDLE"
    DETECT = "DETECT"
    VISION = "VISION"
    ROUTING = "ROUTING"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class ProjectedPoint:
    point: QPointF
    depth: float


def _add(a: Vec3, b: Vec3) -> Vec3:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _subtract(a: Vec3, b: Vec3) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(value: Vec3) -> Vec3:
    length = math.sqrt(_dot(value, value)) or 1.0
    return value[0] / length, value[1] / length, value[2] / length


class DigitalTwinWidget(QWidget):
    """Software-rendered 3D twin with orbit, pan, zoom and a six-axis robot."""

    VIEW_PRESETS = {
        "isometric": (-42.0, 27.0, 10.5, (0.0, 0.0, 1.0)),
        "top": (-90.0, 73.0, 12.0, (0.0, 0.0, 0.4)),
        "front": (-90.0, 8.0, 10.5, (0.0, 0.0, 1.0)),
        "robot": (-145.0, 24.0, 6.5, (3.0, -1.0, 1.2)),
    }

    def __init__(self) -> None:
        super().__init__()
        self.stage = ProcessStage.IDLE
        self.decision: str | None = None
        self.conveyor_running = False
        self.conveyor_command_state = "UNKNOWN"
        self.robot_angles = [30, -35, 68, 0, 35, 0]
        self.layer_visibility = {
            "equipment": True,
            "vision_zones": True,
            "telemetry_labels": True,
        }
        self.yaw = -42.0
        self.pitch = 27.0
        self.distance = 10.5
        self.target: Vec3 = (0.0, 0.0, 1.0)
        self._drag_position: QPointF | None = None
        self._drag_button = Qt.MouseButton.NoButton
        self.setMinimumSize(620, 390)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_process_state(
        self,
        stage: ProcessStage,
        decision: str | None = None,
        conveyor_running: bool | None = None,
    ) -> None:
        self.stage = stage
        self.decision = decision
        if conveyor_running is not None:
            self.conveyor_running = conveyor_running
        self.update()

    def set_joint_angle(self, joint: int, angle: int) -> None:
        if not 0 <= joint < 6:
            raise IndexError("Robot joint index must be from 0 to 5")
        self.robot_angles[joint] = int(angle)
        self.update()

    def set_conveyor_command_state(self, state: str) -> None:
        if state not in {"UNKNOWN", "STOP", "FWD", "REV"}:
            raise ValueError(f"Unknown conveyor state: {state}")
        self.conveyor_command_state = state
        self.conveyor_running = state in {"FWD", "REV"}
        self.update()

    def set_view(self, preset: str) -> None:
        if preset not in self.VIEW_PRESETS:
            raise ValueError(f"Unknown camera preset: {preset}")
        self.yaw, self.pitch, self.distance, self.target = self.VIEW_PRESETS[preset]
        self.update()

    def reset_view(self) -> None:
        self.set_view("isometric")

    def set_layer_visible(self, layer: str, visible: bool) -> None:
        if layer not in self.layer_visibility:
            raise ValueError(f"Unknown Digital Twin layer: {layer}")
        self.layer_visibility[layer] = bool(visible)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#080d12"))
        self._draw_floor(painter)
        if not self.layer_visibility["equipment"]:
            self._draw_overlay(painter)
            return

        polygons: list[tuple[float, QPolygonF, QColor, QColor]] = []
        labels: list[tuple[Vec3, str, QColor]] = []

        self._add_box(polygons, (0.0, 0.0, 0.58), (8.2, 1.65, 0.28), "#31404b")
        self._add_box(polygons, (0.0, 0.0, 0.76), (8.0, 1.45, 0.10), "#465765")
        for x_value in (-3.6, -1.7, 1.7, 3.6):
            for y_value in (-0.62, 0.62):
                self._add_box(
                    polygons,
                    (x_value, y_value, 0.27),
                    (0.18, 0.18, 0.55),
                    "#26323d",
                )

        for x_value in [value * 0.4 for value in range(-9, 10)]:
            self._add_line(
                painter,
                (x_value, -0.68, 0.84),
                (x_value, 0.68, 0.84),
                QColor("#738496"),
                1.2,
            )

        for y_value in (-1.02, 1.02):
            self._add_box(polygons, (-3.2, y_value, 1.15), (0.16, 0.16, 1.45), "#2b6cb0")
        if self.layer_visibility["vision_zones"]:
            self._add_line(
                painter,
                (-3.2, -1.0, 1.25),
                (-3.2, 1.0, 1.25),
                QColor("#f85149"),
                1.5,
                Qt.PenStyle.DashLine,
            )
        labels.append(((-3.2, 0.0, 2.05), "SENSOR S1", QColor("#83b9ec")))

        for y_value in (-1.12, 1.12):
            self._add_box(polygons, (-0.8, y_value, 1.65), (0.16, 0.16, 1.9), "#647787")
        self._add_box(polygons, (-0.8, 0.0, 2.58), (0.20, 2.45, 0.18), "#708596")
        self._add_box(polygons, (-0.8, 0.0, 2.30), (0.55, 0.42, 0.42), "#2f81f7")
        self._add_box(polygons, (-0.8, 0.0, 2.04), (0.19, 0.19, 0.20), "#111820")
        if self.layer_visibility["vision_zones"]:
            self._add_line(
                painter,
                (-0.8, 0.0, 2.0),
                (-0.8, 0.0, 0.86),
                QColor("#2f81f7"),
                1.2,
                Qt.PenStyle.DashLine,
            )
        labels.append(((-0.8, 0.0, 2.90), "CAMERA 2K / VISION", QColor("#8fc1ff")))

        parcel_position = self._parcel_position()
        parcel_color = "#d29922"
        if self.decision == "PASS":
            parcel_color = "#26a269"
        elif self.decision == "REJECT":
            parcel_color = "#f85149"
        self._add_box(polygons, parcel_position, (0.95, 0.72, 0.72), parcel_color)
        labels.append((_add(parcel_position, (0.0, 0.0, 0.55)), "PARCEL A6", QColor(parcel_color)))

        bin_specs = (
            ((4.25, 1.65, 0.58), "BIN PASS", "#26a269"),
            ((4.25, 2.65, 0.58), "BIN DEFECT", "#f85149"),
            ((2.85, 2.65, 0.58), "BIN REVIEW", "#d29922"),
        )
        for center, label, color in bin_specs:
            self._add_box(polygons, center, (1.05, 0.8, 1.0), color)
            labels.append((_add(center, (0.0, 0.0, 0.72)), label, QColor(color)))

        for _depth, polygon, fill, edge in sorted(
            polygons, key=lambda item: item[0], reverse=True
        ):
            painter.setPen(QPen(edge, 1))
            painter.setBrush(fill)
            painter.drawPolygon(polygon)

        for x_value in [value * 0.4 for value in range(-9, 10)]:
            self._add_line(
                painter,
                (x_value, -0.68, 0.84),
                (x_value, 0.68, 0.84),
                QColor("#93a4b3"),
                1.2,
            )

        self._draw_robot(painter, labels)
        if self.layer_visibility["telemetry_labels"]:
            self._draw_labels(painter, labels)
        self._draw_overlay(painter)

    def _draw_floor(self, painter: QPainter) -> None:
        for value in range(-6, 7):
            self._add_line(
                painter,
                (value, -4.0, 0.0),
                (value, 4.0, 0.0),
                QColor("#1b2833"),
                1,
            )
        for value in range(-4, 5):
            self._add_line(
                painter,
                (-6.0, value, 0.0),
                (6.0, value, 0.0),
                QColor("#1b2833"),
                1,
            )
        axes = (
            ((0.0, 0.0, 0.02), (1.3, 0.0, 0.02), QColor("#f85149")),
            ((0.0, 0.0, 0.02), (0.0, 1.3, 0.02), QColor("#26a269")),
            ((0.0, 0.0, 0.02), (0.0, 0.0, 1.3), QColor("#2f81f7")),
        )
        for start, end, color in axes:
            self._add_line(painter, start, end, color, 2)

    def _draw_robot(self, painter: QPainter, labels: list[tuple[Vec3, str, QColor]]) -> None:
        base = (3.15, -2.0, 0.08)
        self._draw_joint(painter, base, 24, QColor("#596b79"))
        yaw = math.radians(self.robot_angles[0])
        shoulder = (base[0], base[1], 0.92)
        elbow = _add(
            shoulder,
            self._direction(yaw, math.radians(52 + self.robot_angles[1] * 0.35), 1.35),
        )
        wrist_1 = _add(
            elbow,
            self._direction(yaw, math.radians(12 + self.robot_angles[2] * 0.25), 1.15),
        )
        wrist_2 = _add(
            wrist_1,
            self._direction(
                yaw + math.radians(self.robot_angles[3] * 0.35), math.radians(-12), 0.46
            ),
        )
        wrist_3 = _add(
            wrist_2,
            self._direction(
                yaw + math.radians(self.robot_angles[4] * 0.25), math.radians(-32), 0.34
            ),
        )
        tool = _add(
            wrist_3,
            self._direction(
                yaw + math.radians(self.robot_angles[5] * 0.5), math.radians(-45), 0.34
            ),
        )
        joints = [base, shoulder, elbow, wrist_1, wrist_2, wrist_3, tool]
        link_colors = ["#485966", "#d9781d", "#e88924", "#d9781d", "#bd6518", "#9f5417"]
        projected_links = []
        for index, (start, end) in enumerate(zip(joints[:-1], joints[1:])):
            start_projected = self._project(start)
            end_projected = self._project(end)
            if start_projected and end_projected:
                projected_links.append(
                    (
                        (start_projected.depth + end_projected.depth) / 2,
                        start_projected.point,
                        end_projected.point,
                        QColor(link_colors[index]),
                        15 if index < 3 else 10,
                    )
                )
        for _depth, start, end, color, width in sorted(
            projected_links, key=lambda item: item[0], reverse=True
        ):
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(start, end)
        for index, joint in enumerate(joints[1:-1], start=1):
            self._draw_joint(painter, joint, 9 if index < 4 else 7, QColor("#f0a04b"))
        self._draw_gripper(painter, tool, yaw)
        labels.append(((3.15, -2.0, 2.85), "ROBOT 6-AXIS", QColor("#f0a04b")))

    def _draw_joint(self, painter: QPainter, position: Vec3, radius: float, color: QColor) -> None:
        projected = self._project(position)
        if projected is None:
            return
        painter.setPen(QPen(color.lighter(135), 2))
        painter.setBrush(color)
        painter.drawEllipse(projected.point, radius, radius)

    def _draw_gripper(self, painter: QPainter, position: Vec3, yaw: float) -> None:
        direction = (-math.sin(yaw) * 0.22, math.cos(yaw) * 0.22, -0.16)
        for sign in (-1, 1):
            end = (
                position[0] + direction[0] * sign,
                position[1] + direction[1] * sign,
                position[2] + direction[2],
            )
            self._add_line(painter, position, end, QColor("#cbd5df"), 4)

    def _draw_labels(self, painter: QPainter, labels: list[tuple[Vec3, str, QColor]]) -> None:
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for position, text, color in labels:
            projected = self._project(position)
            if projected is None:
                continue
            bounds = painter.fontMetrics().boundingRect(text)
            rect = QRectF(
                projected.point.x() - bounds.width() / 2 - 5,
                projected.point.y() - bounds.height() / 2 - 3,
                bounds.width() + 10,
                bounds.height() + 6,
            )
            painter.fillRect(rect, QColor(8, 13, 18, 205))
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_overlay(self, painter: QPainter) -> None:
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        run_text = f"CONVEYOR CMD: {self.conveyor_command_state}"
        run_color = QColor("#26a269") if self.conveyor_running else QColor("#8c9bab")
        painter.setPen(run_color)
        painter.drawText(16, 24, run_text)
        painter.setPen(QColor("#8c9bab"))
        painter.drawText(16, 43, f"STATE: {self.stage.value}   ROBOT: READY")
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(16, self.height() - 30, self.width() - 32, 20),
            Qt.AlignmentFlag.AlignLeft,
            "Kéo chuột trái: xoay  ·  Chuột phải: pan  ·  Con lăn: zoom  ·  Double-click: reset",
        )

    def _parcel_position(self) -> Vec3:
        positions = {
            ProcessStage.IDLE: (-3.8, 0.0, 1.22),
            ProcessStage.DETECT: (-3.1, 0.0, 1.22),
            ProcessStage.VISION: (-0.8, 0.0, 1.22),
            ProcessStage.ROUTING: (1.75, 0.0, 1.22),
            ProcessStage.COMPLETE: (3.1, 0.0, 1.22),
        }
        return positions[self.stage]

    @staticmethod
    def _direction(yaw: float, elevation: float, length: float) -> Vec3:
        horizontal = math.cos(elevation) * length
        return (
            math.cos(yaw) * horizontal,
            math.sin(yaw) * horizontal,
            math.sin(elevation) * length,
        )

    def _add_box(
        self,
        polygons: list[tuple[float, QPolygonF, QColor, QColor]],
        center: Vec3,
        size: Vec3,
        color: str,
    ) -> None:
        x, y, z = center
        half_x, half_y, half_z = size[0] / 2, size[1] / 2, size[2] / 2
        vertices = (
            (x - half_x, y - half_y, z - half_z),
            (x + half_x, y - half_y, z - half_z),
            (x + half_x, y + half_y, z - half_z),
            (x - half_x, y + half_y, z - half_z),
            (x - half_x, y - half_y, z + half_z),
            (x + half_x, y - half_y, z + half_z),
            (x + half_x, y + half_y, z + half_z),
            (x - half_x, y + half_y, z + half_z),
        )
        faces = (
            ((0, 1, 2, 3), 150),
            ((4, 7, 6, 5), 112),
            ((0, 4, 5, 1), 128),
            ((1, 5, 6, 2), 118),
            ((2, 6, 7, 3), 138),
            ((3, 7, 4, 0), 125),
        )
        base_color = QColor(color)
        for face, shade in faces:
            projected = [self._project(vertices[index]) for index in face]
            if any(point is None for point in projected):
                continue
            visible = [point for point in projected if point is not None]
            polygon = QPolygonF([point.point for point in visible])
            depth = sum(point.depth for point in visible) / len(visible)
            polygons.append((depth, polygon, base_color.lighter(shade), base_color.lighter(155)))

    def _add_line(
        self,
        painter: QPainter,
        start: Vec3,
        end: Vec3,
        color: QColor,
        width: float,
        style: Qt.PenStyle = Qt.PenStyle.SolidLine,
    ) -> None:
        start_projected = self._project(start)
        end_projected = self._project(end)
        if start_projected is None or end_projected is None:
            return
        painter.setPen(QPen(color, width, style, Qt.PenCapStyle.RoundCap))
        painter.drawLine(start_projected.point, end_projected.point)

    def _project(self, point: Vec3) -> ProjectedPoint | None:
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        camera = (
            self.target[0] + self.distance * math.cos(pitch) * math.cos(yaw),
            self.target[1] + self.distance * math.cos(pitch) * math.sin(yaw),
            self.target[2] + self.distance * math.sin(pitch),
        )
        forward = _normalize(_subtract(self.target, camera))
        right = _normalize(_cross(forward, (0.0, 0.0, 1.0)))
        up = _cross(right, forward)
        relative = _subtract(point, camera)
        depth = _dot(relative, forward)
        if depth <= 0.1:
            return None
        focal = min(self.width(), self.height()) * 1.12
        screen_x = self.width() * 0.50 + _dot(relative, right) * focal / depth
        screen_y = self.height() * 0.52 - _dot(relative, up) * focal / depth
        return ProjectedPoint(QPointF(screen_x, screen_y), depth)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._drag_position = event.position()
            self._drag_button = event.button()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is None:
            return
        delta = event.position() - self._drag_position
        self._drag_position = event.position()
        if self._drag_button == Qt.MouseButton.LeftButton:
            self.yaw += delta.x() * 0.45
            self.pitch = max(-75.0, min(80.0, self.pitch + delta.y() * 0.35))
        elif self._drag_button == Qt.MouseButton.RightButton:
            scale = self.distance / max(350.0, min(self.width(), self.height()))
            self.target = (
                self.target[0] - delta.x() * scale,
                self.target[1],
                self.target[2] + delta.y() * scale,
            )
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_position = None
        self._drag_button = Qt.MouseButton.NoButton
        self.unsetCursor()

    def mouseDoubleClickEvent(self, _event: QMouseEvent) -> None:
        self.reset_view()

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120.0
        self.distance = max(6.0, min(24.0, self.distance - steps * 0.75))
        self.update()
        event.accept()
