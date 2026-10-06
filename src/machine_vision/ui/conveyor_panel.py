"""Non-blocking manual conveyor controls for the UDP ESP32 firmware."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from machine_vision.controllers.conveyor_udp import (
    ConveyorReply,
    exchange,
    make_command,
    validate_endpoint,
)


class _Request(QThread):
    completed = pyqtSignal(int, object, object)

    def __init__(self, sequence: int, host: str, port: int, command: str, parent=None) -> None:
        super().__init__(parent)
        self.sequence = sequence
        self.host = host
        self.port = port
        self.command = command

    def run(self) -> None:
        try:
            reply = exchange(self.host, self.port, self.command)
            self.completed.emit(self.sequence, reply, None)
        except (OSError, ValueError, UnicodeError) as exc:
            self.completed.emit(self.sequence, None, str(exc))


class ConveyorPanel(QFrame):
    state_changed = pyqtSignal(str, int)
    connection_changed = pyqtSignal(bool)

    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self._sequence = 0
        self._workers: dict[int, _Request] = {}
        self._state = "UNKNOWN"
        self._online = False
        self._motor_commanded = False
        self._stop_queued = False
        self._closing = False
        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(1000)
        self._heartbeat.timeout.connect(self._ping_heartbeat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        title = QLabel("BĂNG TẢI / ESP32 · UDP MANUAL")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        endpoint = QHBoxLayout()
        self.host = QLineEdit(str(config.get("host", "192.168.2.100")))
        self.host.setPlaceholderText("IPv4 ESP32")
        self.host.setToolTip("IP tĩnh của W5500; laptop cùng subnet 192.168.2.0/24")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(config.get("port", 8120)))
        self.port.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.port.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.port.setFixedWidth(104)
        self.port.setToolTip("UDP port (1–65535); nhập trực tiếp, mặc định 8120")
        self._endpoint_value = (self.host.text(), self.port.value())
        self.host.editingFinished.connect(self._endpoint_changed)
        self.port.valueChanged.connect(self._endpoint_changed)
        self.ping_button = QPushButton("PING")
        self.ping_button.setObjectName("secondary")
        self.ping_button.clicked.connect(lambda: self._send("PING"))
        endpoint.addWidget(self.host, 1)
        endpoint.addWidget(self.port)
        endpoint.addWidget(self.ping_button)
        layout.addLayout(endpoint)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("PWM"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, 255)
        self.speed.setValue(int(config.get("default_speed", 150)))
        self.speed_value = QLabel(str(self.speed.value()))
        self.speed_value.setFixedWidth(30)
        self.speed.valueChanged.connect(lambda value: self.speed_value.setText(str(value)))
        speed_row.addWidget(self.speed, 1)
        speed_row.addWidget(self.speed_value)
        layout.addLayout(speed_row)

        buttons = QGridLayout()
        self.forward_button = QPushButton("CHẠY TIẾN")
        self.reverse_button = QPushButton("CHẠY LÙI")
        self.stop_button = QPushButton("DỪNG")
        self.stop_button.setStyleSheet("background:#a83232; border-color:#e16b6b; color:white;")
        self.stop_button.setToolTip("Lệnh STOP qua UDP; KHÔNG thay thế nút dừng khẩn phần cứng.")
        self.forward_button.clicked.connect(lambda: self._send("FWD"))
        self.reverse_button.clicked.connect(lambda: self._send("REV"))
        self.stop_button.clicked.connect(lambda: self._send("STOP"))
        buttons.addWidget(self.forward_button, 0, 0)
        buttons.addWidget(self.reverse_button, 0, 1)
        buttons.addWidget(self.stop_button, 0, 2)
        layout.addLayout(buttons)
        self.status = QLabel("CHƯA KẾT NỐI · Không có telemetry tốc độ thực")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#d29922; font-size:10px;")
        layout.addWidget(self.status)
        self._set_run_buttons(False)

    def _endpoint_changed(self) -> None:
        value = (self.host.text(), self.port.value())
        if value == self._endpoint_value:
            return
        self._endpoint_value = value
        self._heartbeat.stop()
        self._sequence += 1  # Ignore ACKs from the previous endpoint.
        self._state = "UNKNOWN"
        self._online = False
        self._set_run_buttons(False)
        self.status.setText("ĐỊA CHỈ ĐÃ ĐỔI · Nhấn PING để xác nhận ESP32 mới")
        self.state_changed.emit("UNKNOWN", 0)
        self.connection_changed.emit(False)

    def _set_run_buttons(self, enabled: bool) -> None:
        enabled = enabled and self._state != "UNKNOWN" and not self._stop_queued
        self.forward_button.setEnabled(enabled and self._state != "REV")
        self.reverse_button.setEnabled(enabled and self._state != "FWD")
        # STOP remains available even if PING fails or another request is in flight.
        self.stop_button.setEnabled(True)

    def _send(self, action: str) -> None:
        if self._closing:
            return
        if self._workers:
            if action == "STOP":
                self._stop_queued = True
                self._sequence += 1
                self._set_run_buttons(False)
                self.status.setText("DỪNG ĐANG CHỜ · gửi STOP ngay khi yêu cầu hiện tại kết thúc")
            return
        if action in {"FWD", "REV"}:
            if not self._online or self._state == "UNKNOWN":
                return
            if {action, self._state} == {"FWD", "REV"}:
                self.status.setText("Hãy DỪNG và đợi ACK trước khi đảo chiều")
                return
        try:
            host, port = validate_endpoint(self.host.text(), self.port.value())
            command = make_command(action, self.speed.value())
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._sequence += 1
        sequence = self._sequence
        if action != "PING":
            self._set_run_buttons(False)
        if action in {"FWD", "REV"}:
            self._motor_commanded = True
            self.host.setEnabled(False)
            self.port.setEnabled(False)
        self.status.setText(f"ĐANG GỬI {command} → {host}:{port}")
        worker = _Request(sequence, host, port, command, self)
        self._workers[sequence] = worker
        worker.completed.connect(self._on_completed)
        worker.finished.connect(lambda seq=sequence: self._on_finished(seq))
        worker.finished.connect(worker.deleteLater)
        self.ping_button.setEnabled(False)
        worker.start()

    def _on_finished(self, sequence: int) -> None:
        self._workers.pop(sequence, None)
        self.ping_button.setEnabled(True)
        if self._stop_queued and not self._closing:
            self._stop_queued = False
            self._send("STOP")

    def _on_completed(self, sequence: int, reply: ConveyorReply | None, error: str | None) -> None:
        if sequence != self._sequence:
            return  # A later STOP or command superseded this response.
        if error:
            self._heartbeat.stop()
            self._state = "UNKNOWN"
            self._online = False
            self._set_run_buttons(False)
            self.status.setText(f"MẤT XÁC NHẬN: {error} · Kiểm tra băng tải tại chỗ")
            self.state_changed.emit("UNKNOWN", 0)
            self.connection_changed.emit(False)
            return
        assert reply is not None
        self._online = True
        self._heartbeat.start()
        if reply.command == "PING":
            self._set_run_buttons(True)
            self.status.setText(
                f"ONLINE · {reply.raw} · Nhấn DỪNG để xác nhận trước khi chạy"
                if self._state == "UNKNOWN"
                else f"ONLINE · lệnh gần nhất: {self._state} · không có encoder"
            )
            self.connection_changed.emit(True)
            return
        self._state = reply.state or "UNKNOWN"
        if self._state == "STOP":
            self._motor_commanded = False
            self.host.setEnabled(True)
            self.port.setEnabled(True)
        self._set_run_buttons(True)
        self.status.setText(f"XÁC NHẬN · {reply.raw} · PWM lệnh, không phải tốc độ đo")
        self.state_changed.emit(self._state, reply.speed or 0)
        self.connection_changed.emit(True)

    def _ping_heartbeat(self) -> None:
        if self._workers:
            return
        self._send("PING")

    @property
    def state(self) -> str:
        return self._state

    def shutdown(self) -> str | None:
        """Try to stop a motor commanded by this session before closing."""
        self._closing = True
        self._heartbeat.stop()
        for worker in list(self._workers.values()):
            worker.wait(800)
        self._sequence += 1  # Ignore completion signals queued before shutdown.
        self._stop_queued = False
        if self._motor_commanded:
            try:
                exchange(self.host.text(), self.port.value(), "STOP:0")
            except (OSError, ValueError, UnicodeError) as exc:
                self._closing = False
                self._online = False
                self._state = "UNKNOWN"
                self._set_run_buttons(False)
                self.state_changed.emit("UNKNOWN", 0)
                self.connection_changed.emit(False)
                self.status.setText("ĐÓNG ỨNG DỤNG BỊ HỦY · Chưa xác nhận STOP")
                return str(exc)
            self._motor_commanded = False
            self._state = "STOP"
            self.state_changed.emit("STOP", 0)
        return None
