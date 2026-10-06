from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from PyQt6.QtWidgets import QApplication, QTableWidgetItem  # noqa: E402

from machine_vision.app import build_pipeline  # noqa: E402
from machine_vision.config import load_config  # noqa: E402
from machine_vision.ui.digital_twin import ProcessStage  # noqa: E402
from machine_vision.ui.main_window import MainWindow  # noqa: E402


def populate_demo(window: MainWindow, config: dict) -> None:
    samples = sorted((PROJECT / "dataset" / "raw" / "40cm").glob("*.png"))
    if samples:
        frame = cv2.imread(str(samples[0]))
        if frame is not None:
            window.video.show_frame(frame, config["label"]["roi"])
            window.snapshot_video.show_frame(frame)
            window.snapshot_view_button.setEnabled(True)

    window.camera_status.set_state("ONLINE")
    window.controller_status.set_state("NOT CONFIGURED")
    window.frame_state.setText("PASS")
    window.frame_state.setStyleSheet("color:#26a269; font-weight:700;")
    window.connect_button.setText("NGẮT CAMERA")
    window.inspect_button.setEnabled(True)
    window.focus_metric.value.setText("143")
    window.tenengrad_metric.value.setText("1864")
    window.motion_metric.value.setText("1.4")
    window.quality_metric.value.setText("READY")
    window.quality_metric.value.setStyleSheet("color:#26a269;")
    window.throughput_metric.value.setText("128")
    window.success_metric.value.setText("98.4")
    window.pass_metric.value.setText("119")
    window.reject_metric.value.setText("6")
    window.cycle_metric.value.setText("684")
    window.decision_label.setText("LOCAL PASS")
    window.decision_label.setStyleSheet(
        "font-size:23px; font-weight:800; color:#26a269;"
        "background:rgba(38,162,105,35); border-radius:6px; padding:6px 9px;"
    )
    window.waybill_label.setText("SPXVN012345678")
    window.qr_payload_label.setText("SPXVN012345678")
    window.logo_label.setText("OK · 0.92")
    window.damage_label.setText("BÌNH THƯỜNG")
    window.destination_label.setText("LOCAL_TEST")
    window.background_status_label.setText("SẴN SÀNG")
    window.background_status_label.setStyleSheet("color:#26a269; font-weight:700;")
    window.reason_label.setText(
        "QR, logo và tình trạng kiện hợp lệ; đã bỏ qua truy vấn Supabase"
    )
    window._set_twin_process(ProcessStage.COMPLETE, "PASS")

    values = ("10:42:18", "SPXVN012345678", "OK", "PASS", "BIN_01", "Kiện hợp lệ")
    window.history.insertRow(0)
    for column, value in enumerate(values):
        window.history.setItem(0, column, QTableWidgetItem(value))


def main() -> int:
    config = load_config(PROJECT / "config" / "default.yaml").raw
    app = QApplication([])
    pipeline, _warning = build_pipeline(config)
    window = MainWindow(config, pipeline)
    populate_demo(window, config)
    window.resize(1366, 768)
    window.show()
    app.processEvents()
    output_directory = PROJECT.parent / "work"
    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for tab_index, name in enumerate((
        "machinevision-operator.png",
        "machinevision-twin3d.png",
        "machinevision-conveyor.png",
    )):
        window.workspace_tabs.setCurrentIndex(tab_index)
        app.processEvents()
        output = output_directory / name
        if not window.grab().save(str(output)):
            raise RuntimeError(f"Unable to save UI preview to {output}")
        outputs.append(output.resolve())
    print("\n".join(str(output) for output in outputs))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
