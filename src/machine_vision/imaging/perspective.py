from __future__ import annotations

import cv2
import numpy as np


class LabelNotFoundError(RuntimeError):
    pass


def order_quad(points: np.ndarray) -> np.ndarray:
    """Return four points ordered top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    differences = np.diff(pts, axis=1).reshape(-1)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(differences)]
    ordered[3] = pts[np.argmax(differences)]
    return ordered


def warp_quad(image: np.ndarray, points: np.ndarray, width: int, height: int) -> np.ndarray:
    source = order_quad(points)
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, destination)
    return cv2.warpPerspective(image, transform, (width, height), flags=cv2.INTER_CUBIC)


def detect_label_quad(image: np.ndarray, settings: dict) -> np.ndarray:
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(
        gray,
        int(settings.get("canny_low", 50)),
        int(settings.get("canny_high", 150)),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(image.shape[0] * image.shape[1])
    min_area = float(settings.get("min_area_ratio", 0.20)) * image_area

    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(contour) < min_area:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            return order_quad(polygon.reshape(4, 2))
    raise LabelNotFoundError("No rectangular label candidate passed the area gate")


def rectify_label(image: np.ndarray, settings: dict, width: int, height: int) -> np.ndarray:
    points = detect_label_quad(image, settings)
    return warp_quad(image, points, width, height)


def rectify_from_qr_anchor(
    image: np.ndarray,
    qr_corners: np.ndarray,
    target_roi: list[float] | tuple[float, float, float, float],
    width: int,
    height: int,
) -> np.ndarray:
    """Rectify the label plane by mapping a detected QR onto its recipe position."""
    x, y, w, h = target_roi
    destination = np.array(
        [
            [x * width, y * height],
            [(x + w) * width, y * height],
            [(x + w) * width, (y + h) * height],
            [x * width, (y + h) * height],
        ],
        dtype=np.float32,
    )
    source = order_quad(qr_corners)
    transform = cv2.getPerspectiveTransform(source, destination)
    return cv2.warpPerspective(
        image,
        transform,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
