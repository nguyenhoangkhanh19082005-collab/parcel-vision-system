from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from machine_vision.imaging.enhancement import crop_fraction
from machine_vision.models import LogoAssessment


class LogoDetector(Protocol):
    def detect(self, label: np.ndarray) -> tuple[LogoAssessment, np.ndarray]: ...

    def calibrate(
        self, label: np.ndarray, roi: tuple[int, int, int, int]
    ) -> dict[str, object]: ...


class TemplateLogoDetector:
    """Detect a fixed label logo after QR-anchor perspective rectification."""

    def __init__(
        self,
        settings: dict,
        project_root: Path,
        writable_root: Path | None = None,
    ):
        self.settings = settings
        self.project_root = project_root
        self.writable_root = writable_root or project_root
        self.threshold = float(settings.get("threshold", 0.15))
        self.minimum_matches = int(settings.get("min_good_matches", 20))
        self.minimum_inlier_ratio = float(settings.get("min_inlier_ratio", 0.50))
        template_path = Path(str(settings.get("template_path", "")))
        self.bundled_template_path = (
            template_path if template_path.is_absolute() else project_root / template_path
        )
        self.override_template_path = (
            template_path
            if template_path.is_absolute()
            else self.writable_root / template_path
        )
        calibration_path = Path(
            str(settings.get("calibration_path", "config/calibration/logo_calibration.json"))
        )
        self.calibration_path = (
            calibration_path
            if calibration_path.is_absolute()
            else self.writable_root / calibration_path
        )
        self.search_roi = list(settings.get("search_roi", [0.18, 0.08, 0.44, 0.23]))
        self._load_calibration_settings()
        self._sift = cv2.SIFT_create()
        self.template_path = self._active_template_path()
        self.template = None
        self._template_keypoints = []
        self._template_descriptors = None
        self._reload_template()

    def _active_template_path(self) -> Path:
        if self.override_template_path.is_file():
            return self.override_template_path
        return self.bundled_template_path

    def _load_calibration_settings(self) -> None:
        if not self.calibration_path.is_file():
            return
        try:
            payload = json.loads(self.calibration_path.read_text(encoding="utf-8"))
            roi = payload.get("search_roi")
            if isinstance(roi, list) and len(roi) == 4:
                values = [float(value) for value in roi]
                if all(0.0 <= value <= 1.0 for value in values):
                    self.search_roi = values
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return

    def _reload_template(self) -> None:
        self.template_path = self._active_template_path()
        self.template = (
            cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
            if self.template_path.is_file()
            else None
        )
        self._template_keypoints = []
        self._template_descriptors = None
        if self.template is not None:
            self._template_keypoints, self._template_descriptors = self._sift.detectAndCompute(
                self._prepare(self.template), None
            )

    @staticmethod
    def _prepare(image: np.ndarray) -> np.ndarray:
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

    def detect(self, label: np.ndarray) -> tuple[LogoAssessment, np.ndarray]:
        search = crop_fraction(label, self.search_roi)
        if self.template is None:
            return (
                LogoAssessment(
                    calibrated=False,
                    present=None,
                    threshold=self.threshold,
                    reason=f"Logo template not found: {self.template_path}",
                ),
                search,
            )

        prepared = self._prepare(search)
        if self._template_descriptors is None or len(self._template_keypoints) < 4:
            return (
                LogoAssessment(
                    calibrated=False,
                    present=None,
                    threshold=self.threshold,
                    reason="Logo template does not contain enough visual features",
                ),
                search,
            )

        keypoints, descriptors = self._sift.detectAndCompute(prepared, None)
        if descriptors is None or len(keypoints) < 4:
            return (
                LogoAssessment(
                    calibrated=True,
                    present=False,
                    threshold=self.threshold,
                    reason="Expected logo was not detected",
                ),
                search,
            )

        matcher = cv2.BFMatcher()
        pairs = matcher.knnMatch(self._template_descriptors, descriptors, k=2)
        ratio = float(self.settings.get("match_ratio", 0.75))
        good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance]
        inliers = 0
        inlier_ratio = 0.0
        bbox = None
        if len(good) >= 4:
            source = np.float32(
                [self._template_keypoints[match.queryIdx].pt for match in good]
            ).reshape(-1, 1, 2)
            destination = np.float32(
                [keypoints[match.trainIdx].pt for match in good]
            ).reshape(-1, 1, 2)
            homography, mask = cv2.findHomography(source, destination, cv2.RANSAC, 5.0)
            if mask is not None:
                inliers = int(mask.sum())
                inlier_ratio = inliers / len(good)
            if homography is not None:
                height, width = self.template.shape[:2]
                corners = np.float32(
                    [[[0, 0]], [[width, 0]], [[width, height]], [[0, height]]]
                )
                transformed = cv2.perspectiveTransform(corners, homography).astype(np.int32)
                bbox = cv2.boundingRect(transformed)

        score = inliers / max(1, len(self._template_keypoints))
        present = bool(
            len(good) >= self.minimum_matches
            and inlier_ratio >= self.minimum_inlier_ratio
            and score >= self.threshold
        )
        reason = "Expected logo detected" if present else "Expected logo was not detected"
        return (
            LogoAssessment(
                calibrated=True,
                present=present,
                score=float(score),
                threshold=self.threshold,
                bbox=bbox,
                reason=reason,
            ),
            search,
        )

    def calibrate(
        self, label: np.ndarray, roi: tuple[int, int, int, int]
    ) -> dict[str, object]:
        """Persist and immediately activate a template selected on a rectified label."""
        x, y, width, height = roi
        image_height, image_width = label.shape[:2]
        x = max(0, min(int(x), image_width - 1))
        y = max(0, min(int(y), image_height - 1))
        width = max(0, min(int(width), image_width - x))
        height = max(0, min(int(height), image_height - y))
        minimum_width = int(self.settings.get("min_template_width_px", 80))
        minimum_height = int(self.settings.get("min_template_height_px", 30))
        if width < minimum_width or height < minimum_height:
            raise ValueError(
                f"Vùng logo quá nhỏ; cần tối thiểu {minimum_width}x{minimum_height} px"
            )
        crop = label[y : y + height, x : x + width].copy()
        keypoints, descriptors = self._sift.detectAndCompute(self._prepare(crop), None)
        minimum_features = int(self.settings.get("min_template_features", 12))
        if descriptors is None or len(keypoints) < minimum_features:
            raise ValueError(
                "Logo chưa đủ nét hoặc vùng chọn có quá ít đặc trưng: "
                f"{len(keypoints)} / {minimum_features}"
            )

        destination = self.override_template_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup: Path | None = None
        if destination.is_file():
            backup = destination.with_name(
                f"{destination.stem}_backup_{timestamp}{destination.suffix}"
            )
            shutil.copy2(destination, backup)
        elif self.bundled_template_path.is_file() and self.bundled_template_path != destination:
            backup = destination.with_name(
                f"{destination.stem}_factory_backup{destination.suffix}"
            )
            if not backup.exists():
                shutil.copy2(self.bundled_template_path, backup)

        temporary = destination.with_name(
            destination.stem + ".tmp" + destination.suffix
        )
        if not cv2.imwrite(str(temporary), crop):
            raise RuntimeError(f"Không thể lưu template logo: {destination}")
        temporary.replace(destination)

        selected = [
            x / image_width,
            y / image_height,
            width / image_width,
            height / image_height,
        ]
        pad_x = max(0.025, selected[2] * 0.25)
        pad_y = max(0.025, selected[3] * 0.50)
        left = max(0.0, selected[0] - pad_x)
        top = max(0.0, selected[1] - pad_y)
        right = min(1.0, selected[0] + selected[2] + pad_x)
        bottom = min(1.0, selected[1] + selected[3] + pad_y)
        self.search_roi = [left, top, right - left, bottom - top]

        payload = {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "template_path": str(destination),
            "template_roi": selected,
            "search_roi": self.search_roi,
            "image_size": [image_width, image_height],
            "template_size": [width, height],
            "sift_keypoints": len(keypoints),
        }
        self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
        json_temporary = self.calibration_path.with_suffix(".json.tmp")
        json_temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        json_temporary.replace(self.calibration_path)
        self._reload_template()
        return {
            **payload,
            "backup_path": str(backup) if backup is not None else None,
        }
