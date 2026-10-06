from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from machine_vision.imaging.enhancement import crop_fraction
from machine_vision.imaging.focus import assess_focus, is_acceptable
from machine_vision.imaging.perspective import rectify_from_qr_anchor, rectify_label
from machine_vision.models import FocusMetrics, InspectionResult, PackageDetection, ParcelData
from machine_vision.readers.logo_reader import LogoDetector
from machine_vision.readers.qr_reader import QrReader
from machine_vision.services.classifier import ParcelClassifier
from machine_vision.services.damage import DamageDetector
from machine_vision.services.label_parser import find_waybill_in_qr
from machine_vision.services.package_detection import QrAnchoredPackageDetector


class FrameQualityError(RuntimeError):
    pass


class VisionPipeline:
    def __init__(
        self,
        config: dict,
        qr_reader: QrReader,
        logo_detector: LogoDetector,
        damage_detector: DamageDetector,
        classifier: ParcelClassifier,
    ):
        self.config = config
        self.qr_reader = qr_reader
        self.logo_detector = logo_detector
        self.damage_detector = damage_detector
        self.classifier = classifier
        self.package_detector = QrAnchoredPackageDetector(
            self.config.get("package_detection", {}), self.config["label"]
        )
        acquisition = self.config.get("acquisition", {})
        self._bench_mode = False
        self.set_bench_mode(bool(acquisition.get("bench_mode_default", False)))

    @property
    def bench_mode(self) -> bool:
        return self._bench_mode

    def set_bench_mode(self, enabled: bool) -> None:
        """Switch between commissioned conveyor gates and the temporary bench setup."""
        self._bench_mode = bool(enabled)
        set_damage_mode = getattr(self.damage_detector, "set_bench_mode", None)
        if callable(set_damage_mode):
            set_damage_mode(self._bench_mode)

    def damage_reference_ready(self) -> bool:
        ready = getattr(self.damage_detector, "reference_ready", None)
        return bool(ready()) if callable(ready) else True

    def capture_bench_background(self, frame: np.ndarray) -> Path:
        save_reference = getattr(self.damage_detector, "save_bench_reference", None)
        if not callable(save_reference):
            raise RuntimeError("Damage detector does not support bench calibration")
        return save_reference(frame)

    def acquisition_settings(self) -> dict:
        """Return the effective quality-gate settings for the active capture profile."""
        acquisition = dict(self.config["acquisition"])
        bench = acquisition.pop("bench", {})
        acquisition.pop("bench_mode_default", None)
        if self._bench_mode and isinstance(bench, dict):
            acquisition.update(bench)
        return acquisition

    def _quality_error(self, best_metrics: FocusMetrics | None) -> FrameQualityError:
        acquisition = self.acquisition_settings()
        profile = "BENCH 15–30 CM" if self._bench_mode else "AUTO / BĂNG TẢI"
        thresholds = (
            f"ngưỡng Laplacian ≥ {float(acquisition.get('min_laplacian', 0)):.1f}, "
            f"Tenengrad ≥ {float(acquisition.get('min_tenengrad', 0)):.0f}, "
            f"motion ≤ {float(acquisition.get('motion_threshold', float('inf'))):.1f}"
        )
        if best_metrics is None:
            measured = "Không nhận được frame hợp lệ để đo."
        else:
            measured = (
                f"Frame tốt nhất: Laplacian {best_metrics.laplacian:.1f}, "
                f"Tenengrad {best_metrics.tenengrad:.0f}, "
                f"motion {best_metrics.motion:.1f}."
            )
        hint = (
            "Giữ kiện và camera đứng yên khoảng 0,5 giây, tránh ánh sáng phản chiếu rồi thử lại."
            if self._bench_mode
            else "Nếu đang thử camera trên bàn/sàn ở 15–30 cm, hãy bật BENCH 15–30 CM."
        )
        return FrameQualityError(
            f"Không có frame đạt cổng chất lượng {profile}.\n"
            f"{measured}\n{thresholds}.\n{hint}"
        )

    def choose_best_frame(self, frames: Iterable[np.ndarray]) -> tuple[np.ndarray, FocusMetrics]:
        label_cfg = self.config["label"]
        acquisition = self.acquisition_settings()
        best = None
        best_measured = None
        previous = None
        consecutive_stable = 0
        required_stable = max(1, int(acquisition.get("stable_frames", 1)))
        for frame in frames:
            label = crop_fraction(frame, label_cfg["roi"])
            metrics = assess_focus(label, previous)
            previous = label
            if np.isfinite(metrics.motion):
                score = metrics.laplacian + 0.02 * metrics.tenengrad
                if best_measured is None or score > best_measured[0]:
                    best_measured = (score, metrics)
            if is_acceptable(metrics, acquisition):
                consecutive_stable += 1
                if consecutive_stable < required_stable:
                    continue
                score = metrics.laplacian + 0.02 * metrics.tenengrad
                if best is None or score > best[0]:
                    best = (score, frame.copy(), metrics)
            else:
                consecutive_stable = 0
        if best is None:
            measured = best_measured[1] if best_measured is not None else None
            raise self._quality_error(measured)
        return best[1], best[2]

    def detect_package_fast(self, frame: np.ndarray) -> PackageDetection | None:
        return self.package_detector.detect_fast(frame)

    def draw_package_detection(
        self, frame: np.ndarray, detection: PackageDetection
    ) -> np.ndarray:
        return self.package_detector.draw(frame, detection)

    def _prepare_label(
        self, frame: np.ndarray, anchor_qr: object | None = None
    ) -> tuple[np.ndarray, object | None]:
        label_cfg = self.config["label"]
        label = crop_fraction(frame, label_cfg["roi"])
        rectification = label_cfg.get("rectification", {})
        anchor_qr = None
        if rectification.get("enabled", False):
            method = str(rectification.get("method", "contour")).lower()
            if method == "qr_anchor":
                anchor_image = frame
                if anchor_qr is None or getattr(anchor_qr, "corners", None) is None:
                    anchor_qr = self.qr_reader.read(frame)
                if anchor_qr is None or anchor_qr.corners is None:
                    anchor_qr = self.qr_reader.read(label)
                    anchor_image = label
                if anchor_qr is None or anchor_qr.corners is None:
                    raise FrameQualityError("QR anchor was not found for label rectification")
                label = rectify_from_qr_anchor(
                    anchor_image,
                    anchor_qr.corners,
                    rectification["qr_target_roi"],
                    int(label_cfg.get("rectify_width", 1050)),
                    int(label_cfg.get("rectify_height", 1480)),
                )
            else:
                label = rectify_label(
                    label,
                    rectification,
                    int(label_cfg.get("rectify_width", 1600)),
                    int(label_cfg.get("rectify_height", 1000)),
                )
        return label, anchor_qr

    def capture_logo_calibration(self, frames: Iterable[np.ndarray]) -> np.ndarray:
        """Choose a quality frame and return the same rectified label used in inspection."""
        frame, _metrics = self.choose_best_frame(frames)
        label, _anchor_qr = self._prepare_label(frame)
        return label

    def calibrate_logo_template(
        self, label: np.ndarray, roi: tuple[int, int, int, int]
    ) -> dict[str, object]:
        calibrate = getattr(self.logo_detector, "calibrate", None)
        if not callable(calibrate):
            raise RuntimeError("Logo detector does not support operator calibration")
        return calibrate(label, roi)

    def inspect(self, frames: Iterable[np.ndarray]) -> InspectionResult:
        frame, metrics = self.choose_best_frame(frames)
        full_frame_qr = self.qr_reader.read(frame)
        package = self.package_detector.detect(
            frame,
            full_frame_qr.corners if full_frame_qr is not None else None,
        )
        damage, damage_debug = self.damage_detector.inspect(frame, package)
        label_cfg = self.config["label"]
        label, anchor_qr = self._prepare_label(frame, full_frame_qr)
        qr_image = crop_fraction(label, label_cfg["qr_roi"])
        qr = full_frame_qr or self.qr_reader.read(qr_image) or anchor_qr
        logo, logo_image = self.logo_detector.detect(label)
        waybill = find_waybill_in_qr(qr.text if qr else None)

        parcel = ParcelData(
            qr_text=qr.text if qr else None,
            waybill_code=waybill,
            logo=logo,
            damage=damage,
        )
        classification = self.classifier.classify(parcel)
        debug_images = {
            "qr": qr_image,
            "logo": logo_image,
            **damage_debug,
        }
        if package is not None:
            debug_images.setdefault(
                "package_overlay", self.package_detector.draw(frame, package)
            )
        return InspectionResult(
            classification=classification,
            focus=metrics,
            original_frame=frame,
            label_image=label,
            debug_images=debug_images,
        )
