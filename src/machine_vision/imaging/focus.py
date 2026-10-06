from __future__ import annotations

import cv2
import numpy as np

from machine_vision.models import FocusMetrics


def to_gray(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def laplacian_variance(image: np.ndarray) -> float:
    gray = cv2.GaussianBlur(to_gray(image), (3, 3), 0)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def tenengrad(image: np.ndarray) -> float:
    gray = cv2.GaussianBlur(to_gray(image), (3, 3), 0)
    sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(sx * sx + sy * sy))


def motion_score(previous: np.ndarray | None, current: np.ndarray) -> float:
    if previous is None:
        # A single frame cannot prove that the parcel has stopped.
        return float("inf")
    a = cv2.resize(to_gray(previous), (320, 180))
    b = cv2.resize(to_gray(current), (320, 180))
    return float(cv2.absdiff(a, b).mean())


def highlight_ratio(image: np.ndarray, threshold: int = 250) -> float:
    gray = to_gray(image)
    return float(np.count_nonzero(gray >= threshold) / gray.size)


def assess_focus(image: np.ndarray, previous: np.ndarray | None = None) -> FocusMetrics:
    return FocusMetrics(
        laplacian=laplacian_variance(image),
        tenengrad=tenengrad(image),
        motion=motion_score(previous, image),
        highlight_ratio=highlight_ratio(image),
    )


def focus_peaking(
    image: np.ndarray,
    threshold: float = 80.0,
    roi: tuple[int, int, int, int] | None = None,
    percentile: float = 92.0,
) -> np.ndarray:
    """Highlight only the strongest in-focus edges inside the useful target area.

    A fixed Sobel threshold painted the floor, hands and every printed character.
    The adaptive percentile keeps the overlay sparse while ``roi`` confines it to
    the detected parcel (or label search area before the first detection).
    """
    gray = cv2.GaussianBlur(to_gray(image), (3, 3), 0)
    sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(sx, sy)
    allowed = np.zeros(gray.shape, dtype=np.uint8)
    if roi is None:
        allowed[:] = 255
        values = magnitude.ravel()
    else:
        x, y, width, height = roi
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(gray.shape[1], x + width), min(gray.shape[0], y + height)
        if x1 <= x0 or y1 <= y0:
            return image.copy()
        allowed[y0:y1, x0:x1] = 255
        values = magnitude[y0:y1, x0:x1].ravel()
    nonzero = values[values > 0]
    adaptive = float(np.percentile(nonzero, percentile)) if nonzero.size else threshold
    effective = max(float(threshold), adaptive)
    peaks = np.uint8((magnitude >= effective) & (allowed > 0)) * 255
    peaks = cv2.dilate(
        peaks, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)), iterations=1
    )
    peaks = cv2.bitwise_and(peaks, allowed)
    color = np.zeros_like(image)
    color[:, :] = (40, 225, 255)
    blended = cv2.addWeighted(image, 0.30, color, 0.70, 0)
    overlay = image.copy()
    overlay[peaks > 0] = blended[peaks > 0]
    return overlay


def is_acceptable(metrics: FocusMetrics, settings: dict) -> bool:
    return (
        metrics.laplacian >= float(settings.get("min_laplacian", 0))
        and metrics.tenengrad >= float(settings.get("min_tenengrad", 0))
        and metrics.motion <= float(settings.get("motion_threshold", float("inf")))
        and metrics.highlight_ratio <= float(settings.get("max_highlight_ratio", 1.0))
    )
