from __future__ import annotations

import cv2
import numpy as np

from machine_vision.imaging.perspective import order_quad
from machine_vision.models import PackageDetection


class QrAnchoredPackageDetector:
    """Locate the parcel carrying a detected QR without a fixed parcel ROI.

    The QR gives an unambiguous target when more than one parcel is visible.  Its
    known position on the A6 label estimates the label rectangle; strong vertical
    carton edges on either side then expand that rectangle to the parcel box.
    """

    def __init__(self, settings: dict, label_settings: dict):
        self.settings = settings
        rectification = label_settings.get("rectification", {})
        self.qr_target_roi = tuple(
            float(value)
            for value in rectification.get(
                "qr_target_roi", [0.70, 0.54, 0.20, 0.20]
            )
        )
        self._fast_qr = cv2.QRCodeDetector()
        try:
            import zxingcpp  # type: ignore
        except ImportError:
            zxingcpp = None
        self._zxing = zxingcpp

    def detect_fast(self, frame: np.ndarray) -> PackageDetection | None:
        """Low-cost QR geometry detection for the live preview (no decoding)."""
        height, width = frame.shape[:2]
        maximum = max(height, width)
        scale = min(1.0, float(self.settings.get("live_max_dimension", 960)) / maximum)
        small = (
            frame
            if scale >= 0.999
            else cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        )
        if self._zxing is not None:
            candidates: list[tuple[float, np.ndarray]] = []
            for value in self._zxing.read_barcodes(small):
                if "QR" not in str(value.format).upper():
                    continue
                position = value.position
                corners = np.array(
                    [
                        [position.top_left.x, position.top_left.y],
                        [position.top_right.x, position.top_right.y],
                        [position.bottom_right.x, position.bottom_right.y],
                        [position.bottom_left.x, position.bottom_left.y],
                    ],
                    dtype=np.float32,
                )
                area = abs(float(cv2.contourArea(corners)))
                center = corners.mean(axis=0)
                centrality = 1.0 - min(
                    0.8,
                    abs(float(center[0]) - small.shape[1] / 2) / small.shape[1],
                )
                border = float(self.settings.get("live_border_margin_ratio", 0.015))
                inside = (
                    corners[:, 0].min() >= border * small.shape[1]
                    and corners[:, 0].max() <= (1.0 - border) * small.shape[1]
                    and corners[:, 1].min() >= border * small.shape[0]
                    and corners[:, 1].max() <= (1.0 - border) * small.shape[0]
                )
                candidates.append((area * centrality * (1.0 if inside else 0.25), corners))
            if candidates:
                corners = max(candidates, key=lambda item: item[0])[1] / scale
                return self.detect(frame, corners)

        found, points = self._fast_qr.detect(small)
        if not found or points is None:
            return None
        corners = np.asarray(points, dtype=np.float32).reshape(4, 2) / scale
        return self.detect(frame, corners)

    def detect(
        self, frame: np.ndarray, qr_corners: np.ndarray | None
    ) -> PackageDetection | None:
        if qr_corners is None:
            return None
        label_bbox = self._label_bbox(frame.shape, qr_corners)
        if label_bbox is None:
            return None

        lx, ly, lw, lh = label_bbox
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(
            gray,
            int(self.settings.get("canny_low", 40)),
            int(self.settings.get("canny_high", 120)),
        )

        vertical_start = max(0, ly + int(0.04 * lh))
        vertical_end = min(frame.shape[0], ly + int(0.96 * lh))
        projection = np.count_nonzero(
            edges[vertical_start:vertical_end], axis=0
        ).astype(np.float32)
        projection = self._smooth(projection, int(self.settings.get("projection_blur", 41)))

        gap = max(8, int(0.04 * lw))
        expansion = float(self.settings.get("max_side_expansion", 1.15))
        left_range = (
            max(0, lx - int(expansion * lw)),
            max(1, lx - gap),
        )
        right_range = (
            min(frame.shape[1] - 1, lx + lw + gap),
            min(frame.shape[1], lx + lw + int(expansion * lw)),
        )
        left = self._nearest_strong_cluster(projection, left_range, from_right=True)
        right = self._nearest_strong_cluster(projection, right_range, from_right=False)

        fallback_x = float(self.settings.get("fallback_side_expansion", 0.38))
        x0 = left if left is not None else lx - int(fallback_x * lw)
        x1 = right if right is not None else lx + lw + int(fallback_x * lw)
        x0 = max(0, min(int(x0), lx))
        x1 = min(frame.shape[1] - 1, max(int(x1), lx + lw))

        y_padding = float(self.settings.get("vertical_padding_ratio", 0.025))
        y0 = max(0, ly - int(y_padding * lh))
        y1 = min(frame.shape[0] - 1, ly + lh + int(y_padding * lh))
        if x1 - x0 < 32 or y1 - y0 < 32:
            return None

        found_edges = int(left is not None) + int(right is not None)
        confidence = min(0.98, 0.62 + 0.16 * found_edges)
        return PackageDetection(
            bbox=(x0, y0, x1 - x0 + 1, y1 - y0 + 1),
            label_bbox=label_bbox,
            confidence=confidence,
            qr_corners=order_quad(qr_corners),
        )

    def draw(self, frame: np.ndarray, detection: PackageDetection) -> np.ndarray:
        overlay = frame.copy()
        x, y, width, height = detection.bbox
        lx, ly, lw, lh = detection.label_bbox
        color = (55, 220, 125)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 4)
        cv2.rectangle(overlay, (lx, ly), (lx + lw, ly + lh), (255, 170, 45), 2)
        caption = f"KIEN HANG  {detection.confidence * 100:.0f}%"
        baseline_y = max(30, y - 12)
        cv2.rectangle(
            overlay,
            (x, baseline_y - 28),
            (x + 260, baseline_y + 5),
            (8, 20, 28),
            cv2.FILLED,
        )
        cv2.putText(
            overlay,
            caption,
            (x + 8, baseline_y - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            color,
            2,
            cv2.LINE_AA,
        )
        return overlay

    def _label_bbox(
        self, frame_shape: tuple[int, ...], qr_corners: np.ndarray
    ) -> tuple[int, int, int, int] | None:
        qx, qy, qw, qh = self.qr_target_roi
        destination_qr = np.array(
            [
                [qx, qy],
                [qx + qw, qy],
                [qx + qw, qy + qh],
                [qx, qy + qh],
            ],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(destination_qr, order_quad(qr_corners))
        unit_label = np.array(
            [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]],
            dtype=np.float32,
        )
        polygon = cv2.perspectiveTransform(unit_label, transform).reshape(4, 2)
        x0 = max(0, int(np.floor(polygon[:, 0].min())))
        y0 = max(0, int(np.floor(polygon[:, 1].min())))
        x1 = min(frame_shape[1] - 1, int(np.ceil(polygon[:, 0].max())))
        y1 = min(frame_shape[0] - 1, int(np.ceil(polygon[:, 1].max())))
        if x1 - x0 < 40 or y1 - y0 < 40:
            return None
        return x0, y0, x1 - x0 + 1, y1 - y0 + 1

    def _nearest_strong_cluster(
        self,
        projection: np.ndarray,
        limits: tuple[int, int],
        *,
        from_right: bool,
    ) -> int | None:
        start, end = limits
        if end - start < 3:
            return None
        values = projection[start:end]
        peak = float(values.max(initial=0.0))
        absolute = float(self.settings.get("min_edge_projection", 12.0))
        threshold = max(absolute, peak * float(self.settings.get("relative_edge_projection", 0.25)))
        active = values >= threshold
        clusters: list[tuple[int, int]] = []
        cluster_start: int | None = None
        for index, enabled in enumerate(active):
            if enabled and cluster_start is None:
                cluster_start = index
            elif not enabled and cluster_start is not None:
                clusters.append((cluster_start, index))
                cluster_start = None
        if cluster_start is not None:
            clusters.append((cluster_start, len(active)))
        if not clusters:
            return None
        cluster = clusters[-1] if from_right else clusters[0]
        local = values[cluster[0] : cluster[1]]
        return start + cluster[0] + int(np.argmax(local))

    @staticmethod
    def _smooth(values: np.ndarray, kernel_size: int) -> np.ndarray:
        kernel_size = max(3, kernel_size)
        kernel_size = kernel_size if kernel_size % 2 else kernel_size + 1
        return cv2.GaussianBlur(values.reshape(1, -1), (kernel_size, 1), 0).ravel()
