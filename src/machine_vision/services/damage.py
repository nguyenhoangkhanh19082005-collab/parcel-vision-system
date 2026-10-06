from __future__ import annotations

from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from machine_vision.imaging.enhancement import crop_fraction
from machine_vision.models import DamageAssessment, PackageDetection


class DamageDetector(Protocol):
    def inspect(
        self, frame: np.ndarray, package: PackageDetection | None = None
    ) -> tuple[DamageAssessment, dict[str, np.ndarray]]: ...

    def set_bench_mode(self, enabled: bool) -> None: ...

    def save_bench_reference(self, frame: np.ndarray) -> Path: ...

    def reference_ready(self) -> bool: ...


class PackageDamageDetector:
    """Background-difference shape inspection for dents, deformation and edge tears."""

    def __init__(
        self, settings: dict, project_root: Path, writable_root: Path | None = None
    ):
        self.settings = settings
        self.project_root = project_root
        self.writable_root = writable_root or project_root
        reference_path = Path(str(settings.get("background_path", "")))
        self.reference_path = (
            reference_path if reference_path.is_absolute() else project_root / reference_path
        )
        self.production_reference = (
            cv2.imread(str(self.reference_path)) if self.reference_path.is_file() else None
        )
        bench_path = Path(
            str(settings.get("bench_background_path", "config/calibration/empty_bench.png"))
        )
        self.bench_reference_path = (
            bench_path if bench_path.is_absolute() else self.writable_root / bench_path
        )
        bundled_bench_path = bench_path if bench_path.is_absolute() else project_root / bench_path
        bench_source = (
            self.bench_reference_path
            if self.bench_reference_path.is_file()
            else bundled_bench_path
        )
        self.bench_reference = (
            cv2.imread(str(bench_source)) if bench_source.is_file() else None
        )
        self._bench_mode = False
        self.reference = self.production_reference

    def set_bench_mode(self, enabled: bool) -> None:
        self._bench_mode = bool(enabled)
        self.reference = self.bench_reference if self._bench_mode else self.production_reference

    def reference_ready(self) -> bool:
        return self.reference is not None

    def save_bench_reference(self, frame: np.ndarray) -> Path:
        self.bench_reference_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.bench_reference_path.with_name(
            self.bench_reference_path.stem + ".tmp" + self.bench_reference_path.suffix
        )
        if not cv2.imwrite(str(temporary), frame):
            raise RuntimeError(f"Unable to save bench background: {self.bench_reference_path}")
        temporary.replace(self.bench_reference_path)
        self.bench_reference = frame.copy()
        if self._bench_mode:
            self.reference = self.bench_reference
        return self.bench_reference_path

    @staticmethod
    def _clip_box(
        box: tuple[int, int, int, int], shape: tuple[int, ...]
    ) -> tuple[int, int, int, int] | None:
        x, y, width, height = box
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(shape[1], x + width), min(shape[0], y + height)
        if x1 - x0 < 20 or y1 - y0 < 20:
            return None
        return x0, y0, x1 - x0, y1 - y0

    def _surface_holes(
        self,
        image: np.ndarray,
        label_box: tuple[int, int, int, int] | None,
    ) -> tuple[list[np.ndarray], np.ndarray, dict[str, float]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        valid = np.full(gray.shape, 255, dtype=np.uint8)
        if label_box is not None:
            x, y, width, height = label_box
            padding = int(self.settings.get("label_mask_padding_px", 10))
            cv2.rectangle(
                valid,
                (max(0, x - padding), max(0, y - padding)),
                (
                    min(gray.shape[1] - 1, x + width + padding),
                    min(gray.shape[0] - 1, y + height + padding),
                ),
                0,
                cv2.FILLED,
            )
        samples = gray[valid > 0]
        if samples.size == 0:
            return [], np.zeros_like(gray), {"surface_dark_threshold": 0.0}
        median = float(np.median(samples))
        dark_threshold = float(
            np.clip(
                median - float(self.settings.get("surface_hole_contrast", 45)),
                float(self.settings.get("surface_hole_min_threshold", 35)),
                float(self.settings.get("surface_hole_max_threshold", 115)),
            )
        )
        mask = np.uint8((gray < dark_threshold) & (valid > 0)) * 255
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = float(mask.size)
        minimum = float(self.settings.get("surface_hole_min_area_ratio", 0.00020)) * image_area
        maximum = float(self.settings.get("surface_hole_max_area_ratio", 0.020)) * image_area
        maximum_aspect = float(self.settings.get("surface_hole_max_aspect", 3.2))
        minimum_fill = float(self.settings.get("surface_hole_min_fill", 0.30))
        selected: list[np.ndarray] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            x, y, width, height = cv2.boundingRect(contour)
            aspect = max(width / max(height, 1), height / max(width, 1))
            fill = area / max(1.0, float(width * height))
            if minimum <= area <= maximum and aspect <= maximum_aspect and fill >= minimum_fill:
                selected.append(contour)
        largest = max((cv2.contourArea(item) for item in selected), default=0.0)
        return selected, mask, {
            "surface_dark_threshold": dark_threshold,
            "surface_holes": float(len(selected)),
            "surface_hole_area_ratio": float(largest / image_area),
        }

    def _target_shape_metrics(
        self, image: np.ndarray, reference: np.ndarray | None
    ) -> tuple[dict[str, float], tuple[str, ...], np.ndarray]:
        if reference is None:
            return {}, (), np.zeros(image.shape[:2], dtype=np.uint8)
        if reference.shape[:2] != image.shape[:2]:
            reference = cv2.resize(reference, (image.shape[1], image.shape[0]))
        blur_size = int(self.settings.get("blur_kernel", 9))
        blur_size = blur_size if blur_size % 2 else blur_size + 1
        current = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (blur_size, blur_size), 0)
        baseline = cv2.GaussianBlur(
            cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), (blur_size, blur_size), 0
        )
        difference = cv2.absdiff(current, baseline)
        mask = cv2.threshold(
            difference, int(self.settings.get("difference_threshold", 25)), 255, cv2.THRESH_BINARY
        )[1]
        kernel_size = int(self.settings.get("morphology_kernel", 11))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {}, (), mask
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        if area < float(self.settings.get("target_shape_min_area_ratio", 0.25)) * mask.size:
            return {}, (), mask
        rotated = cv2.minAreaRect(contour)
        rect_area = max(1.0, float(rotated[1][0] * rotated[1][1]))
        hull_area = max(1.0, float(cv2.contourArea(cv2.convexHull(contour))))
        perimeter = max(1.0, float(cv2.arcLength(contour, True)))
        vertices = len(
            cv2.approxPolyDP(
                contour,
                float(self.settings.get("approx_epsilon_ratio", 0.025)) * perimeter,
                True,
            )
        )
        rectangularity = area / rect_area
        solidity = area / hull_area
        types: list[str] = []
        if rectangularity < float(self.settings.get("min_rectangularity", 0.82)):
            types.append("deformation")
        if solidity < float(self.settings.get("min_solidity", 0.94)):
            types.append("dent_or_edge_tear")
        if vertices > int(self.settings.get("max_vertices", 8)):
            types.append("irregular_outline")
        return {
            "area_ratio": float(area / mask.size),
            "rectangularity": float(rectangularity),
            "solidity": float(solidity),
            "vertices": float(vertices),
        }, tuple(types), mask

    def _inspect_target(
        self, frame: np.ndarray, package: PackageDetection
    ) -> tuple[DamageAssessment, dict[str, np.ndarray]]:
        clipped = self._clip_box(package.bbox, frame.shape)
        if clipped is None:
            return (
                DamageAssessment(True, None, reason="Detected package box is outside the image"),
                {"damage_roi": frame},
            )
        x, y, width, height = clipped
        image = frame[y : y + height, x : x + width]
        lx, ly, lw, lh = package.label_bbox
        label_local = (lx - x, ly - y, lw, lh)
        holes, hole_mask, hole_metrics = self._surface_holes(image, label_local)

        reference_crop = None
        if self.reference is not None:
            reference = self.reference
            if reference.shape[:2] != frame.shape[:2]:
                reference = cv2.resize(reference, (frame.shape[1], frame.shape[0]))
            reference_crop = reference[y : y + height, x : x + width]
        shape_metrics, shape_types, shape_mask = self._target_shape_metrics(
            image, reference_crop
        )
        damage_types = list(shape_types)
        if holes:
            damage_types.append("hole_or_puncture")
        damage_types = list(dict.fromkeys(damage_types))

        overlay = frame.copy()
        parcel_color = (0, 0, 255) if damage_types else (55, 220, 125)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), parcel_color, 4)
        cv2.rectangle(overlay, (lx, ly), (lx + lw, ly + lh), (255, 170, 45), 2)
        cv2.putText(
            overlay,
            f"KIEN HANG {package.confidence * 100:.0f}%",
            (x + 8, max(30, y - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            parcel_color,
            2,
            cv2.LINE_AA,
        )
        for contour in holes:
            translated = contour + np.array([[[x, y]]], dtype=np.int32)
            cv2.drawContours(overlay, [translated], -1, (0, 0, 255), 4)
            hx, hy, hw, hh = cv2.boundingRect(translated)
            cv2.rectangle(overlay, (hx, hy), (hx + hw, hy + hh), (0, 0, 255), 3)
            cv2.putText(
                overlay,
                "THUNG LO",
                (max(x, hx - 2), max(y + 25, hy - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        metrics = {**shape_metrics, **hole_metrics, "package_confidence": package.confidence}
        shape_ready = bool(shape_metrics)
        if damage_types:
            damaged: bool | None = True
            reason = "Visible package defect detected: " + ", ".join(damage_types)
        elif shape_ready:
            damaged = False
            reason = "Target parcel surface and outline passed the configured gates"
        else:
            damaged = None
            reason = "Target parcel found; capture an empty-scene reference for shape inspection"
        confidence = min(
            1.0,
            max(
                package.confidence,
                hole_metrics.get("surface_hole_area_ratio", 0.0)
                / max(float(self.settings.get("surface_hole_min_area_ratio", 0.00020)), 1e-6),
            ),
        )
        return (
            DamageAssessment(
                calibrated=True,
                damaged=damaged,
                damage_types=tuple(damage_types),
                confidence=float(confidence),
                metrics=metrics,
                bbox=clipped,
                reason=reason,
            ),
            {
                "damage_roi": image,
                "damage_mask": shape_mask,
                "surface_hole_mask": hole_mask,
                "damage_overlay": overlay,
            },
        )

    def inspect(
        self, frame: np.ndarray, package: PackageDetection | None = None
    ) -> tuple[DamageAssessment, dict[str, np.ndarray]]:
        if package is not None:
            return self._inspect_target(frame, package)
        roi = self.settings.get("roi", [0.02, 0.02, 0.96, 0.96])
        image = crop_fraction(frame, roi)
        if self.reference is None:
            missing_path = self.bench_reference_path if self._bench_mode else self.reference_path
            return (
                DamageAssessment(
                    calibrated=False,
                    damaged=None,
                    reason=f"Empty-scene reference not found: {missing_path}",
                ),
                {"damage_roi": image},
            )

        reference = crop_fraction(self.reference, roi)
        if reference.shape[:2] != image.shape[:2]:
            reference = cv2.resize(reference, (image.shape[1], image.shape[0]))

        blur_size = int(self.settings.get("blur_kernel", 9))
        blur_size = blur_size if blur_size % 2 else blur_size + 1
        current_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        current_gray = cv2.GaussianBlur(current_gray, (blur_size, blur_size), 0)
        reference_gray = cv2.GaussianBlur(reference_gray, (blur_size, blur_size), 0)
        difference = cv2.absdiff(current_gray, reference_gray)
        threshold = int(self.settings.get("difference_threshold", 25))
        mask = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)[1]
        kernel_size = int(self.settings.get("morphology_kernel", 11))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )
        shape_mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(shape_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        minimum_area = float(self.settings.get("min_package_area_ratio", 0.08)) * mask.size
        candidates = [contour for contour in contours if cv2.contourArea(contour) >= minimum_area]
        if not candidates:
            return (
                DamageAssessment(
                    calibrated=True,
                    damaged=None,
                    reason="Package contour was not found in the damage ROI",
                ),
                {"damage_roi": image, "damage_mask": mask},
            )

        contour = max(candidates, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        rotated = cv2.minAreaRect(contour)
        rect_area = max(1.0, float(rotated[1][0] * rotated[1][1]))
        hull = cv2.convexHull(contour)
        hull_area = max(1.0, float(cv2.contourArea(hull)))
        perimeter = max(1.0, float(cv2.arcLength(contour, True)))
        epsilon = float(self.settings.get("approx_epsilon_ratio", 0.025)) * perimeter
        vertices = len(cv2.approxPolyDP(contour, epsilon, True))
        rectangularity = area / rect_area
        solidity = area / hull_area
        area_ratio = area / mask.size

        minimum_rectangularity = float(self.settings.get("min_rectangularity", 0.82))
        minimum_solidity = float(self.settings.get("min_solidity", 0.94))
        maximum_vertices = int(self.settings.get("max_vertices", 8))
        minimum_hole_ratio = float(self.settings.get("min_hole_area_ratio", 0.002))
        hole_margin = max(3, int(self.settings.get("hole_border_margin_px", 9)))
        hole_margin = hole_margin if hole_margin % 2 else hole_margin + 1
        filled_package = np.zeros_like(mask)
        cv2.drawContours(filled_package, [contour], -1, 255, cv2.FILLED)
        interior = cv2.erode(
            filled_package,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (hole_margin, hole_margin)),
        )
        void_mask = cv2.bitwise_and(interior, cv2.bitwise_not(shape_mask))
        void_contours, _ = cv2.findContours(
            void_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        minimum_hole_area = minimum_hole_ratio * area
        hole_contours = [
            item for item in void_contours if cv2.contourArea(item) >= minimum_hole_area
        ]
        hole_area_ratio = (
            max((cv2.contourArea(item) for item in hole_contours), default=0.0) / area
        )
        damage_types: list[str] = []
        if rectangularity < minimum_rectangularity:
            damage_types.append("deformation")
        if solidity < minimum_solidity:
            damage_types.append("dent_or_edge_tear")
        if vertices > maximum_vertices:
            damage_types.append("irregular_outline")
        if hole_contours:
            damage_types.append("hole_or_puncture")

        deficits = (
            max(0.0, minimum_rectangularity - rectangularity)
            / max(minimum_rectangularity, 1e-6),
            max(0.0, minimum_solidity - solidity) / max(minimum_solidity, 1e-6),
            max(0.0, vertices - maximum_vertices) / max(maximum_vertices, 1),
            min(1.0, hole_area_ratio / max(minimum_hole_ratio, 1e-6)),
        )
        confidence = min(1.0, max(deficits) * 4.0) if damage_types else min(
            1.0,
            min(
                rectangularity / max(minimum_rectangularity, 1e-6),
                solidity / max(minimum_solidity, 1e-6),
            ),
        )
        x, y, width, height = cv2.boundingRect(contour)
        border_margin = int(self.settings.get("border_margin_px", 10))
        touches_border = (
            x <= border_margin
            or y <= border_margin
            or x + width >= image.shape[1] - border_margin
            or y + height >= image.shape[0] - border_margin
        )
        overlay = image.copy()
        color = (0, 0, 255) if damage_types else (0, 200, 80)
        cv2.drawContours(overlay, [contour], -1, color, 3)
        cv2.polylines(overlay, [cv2.boxPoints(rotated).astype(np.int32)], True, (255, 160, 0), 2)
        if hole_contours:
            cv2.drawContours(overlay, hole_contours, -1, (0, 0, 255), 3)
        debug = {
            "damage_roi": image,
            "damage_mask": mask,
            "damage_overlay": overlay,
            "damage_holes": void_mask,
        }
        if touches_border and self.settings.get("require_full_contour", True):
            return (
                DamageAssessment(
                    calibrated=True,
                    damaged=None,
                    metrics={
                        "area_ratio": float(area_ratio),
                        "rectangularity": float(rectangularity),
                        "solidity": float(solidity),
                        "vertices": float(vertices),
                        "hole_area_ratio": float(hole_area_ratio),
                        "holes": float(len(hole_contours)),
                    },
                    bbox=(x, y, width, height),
                    reason="The full package outline is not visible inside the damage ROI",
                ),
                debug,
            )
        reason = (
            "Package shape defect detected: " + ", ".join(damage_types)
            if damage_types
            else "Package outline passed the configured shape gates"
        )
        assessment = DamageAssessment(
            calibrated=True,
            damaged=bool(damage_types),
            damage_types=tuple(damage_types),
            confidence=float(confidence),
            metrics={
                "area_ratio": float(area_ratio),
                "rectangularity": float(rectangularity),
                "solidity": float(solidity),
                "vertices": float(vertices),
                "hole_area_ratio": float(hole_area_ratio),
                "holes": float(len(hole_contours)),
            },
            bbox=(x, y, width, height),
            reason=reason,
        )
        return assessment, debug
