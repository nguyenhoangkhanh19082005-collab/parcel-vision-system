from __future__ import annotations

import cv2
import numpy as np


def crop_fraction(image: np.ndarray, roi: list[float] | tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x, y, w, h = roi
    x1, y1 = int(x * width), int(y * height)
    x2, y2 = int((x + w) * width), int((y + h) * height)
    return image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)].copy()


def grayscale(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def clahe(image: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(grayscale(image))


def unsharp_mask(image: np.ndarray, sigma: float = 1.0, amount: float = 0.5) -> np.ndarray:
    base = grayscale(image)
    blurred = cv2.GaussianBlur(base, (0, 0), sigma)
    return cv2.addWeighted(base, 1.0 + amount, blurred, -amount, 0)


def qr_variants(image: np.ndarray, upscale: float = 2.0, inverted: bool = True) -> list[np.ndarray]:
    base = grayscale(image)
    contrast = clahe(base)
    sharp = unsharp_mask(contrast)
    scaled = cv2.resize(sharp, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    otsu = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptive = cv2.adaptiveThreshold(
        scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    variants = [base, contrast, sharp, scaled, otsu, adaptive]
    if inverted:
        variants.extend(cv2.bitwise_not(item) for item in (scaled, otsu, adaptive))
    return variants
