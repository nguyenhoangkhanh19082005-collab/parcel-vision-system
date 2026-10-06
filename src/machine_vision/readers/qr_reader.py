from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from machine_vision.imaging.enhancement import qr_variants


@dataclass(frozen=True)
class QrRead:
    text: str
    format: str
    variant_index: int
    corners: np.ndarray | None = None


class QrReader:
    """ZXing-C++ reader with OpenCV fallback and preprocessing variants."""

    def __init__(self, settings: dict):
        self.settings = settings
        self._opencv = cv2.QRCodeDetector()
        try:
            import zxingcpp  # type: ignore
        except ImportError:
            zxingcpp = None
        self._zxing = zxingcpp

    def read(self, image: np.ndarray) -> QrRead | None:
        configured = self.settings.get("upscales")
        upscales = (
            configured
            if isinstance(configured, list) and configured
            else [self.settings.get("upscale", 2.0)]
        )
        variant_index = 0
        for upscale in upscales:
            variants = qr_variants(
                image,
                upscale=float(upscale),
                inverted=bool(self.settings.get("try_inverted", True)),
            )
            for variant in variants:
                result = self._read_one(variant)
                if result:
                    text, code_format, corners = result
                    if corners is not None:
                        scale_x = image.shape[1] / variant.shape[1]
                        scale_y = image.shape[0] / variant.shape[0]
                        corners = corners * np.array([scale_x, scale_y], dtype=np.float32)
                    return QrRead(text, code_format, variant_index, corners)
                variant_index += 1
        return None

    def _read_one(self, image: np.ndarray) -> tuple[str, str, np.ndarray | None] | None:
        if self._zxing is not None:
            results = self._zxing.read_barcodes(image)
            qr_results = [value for value in results if "QR" in str(value.format).upper()]
            if qr_results:
                value = qr_results[0]
                text = value.text.strip()
                if text:
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
                    return text, str(value.format), corners

        text, points, _straight = self._opencv.detectAndDecode(image)
        if text.strip():
            corners = None if points is None else np.asarray(points, dtype=np.float32).reshape(4, 2)
            return text.strip(), "QR_CODE", corners
        return None
