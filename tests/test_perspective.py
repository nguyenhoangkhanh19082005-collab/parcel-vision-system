import cv2
import numpy as np

from machine_vision.imaging.perspective import order_quad, rectify_from_qr_anchor, rectify_label


def test_order_quad_returns_consistent_order():
    points = np.array([[90, 80], [10, 10], [100, 10], [5, 90]], dtype=np.float32)
    ordered = order_quad(points)
    assert np.array_equal(ordered[0], [10, 10])
    assert np.array_equal(ordered[1], [100, 10])
    assert np.array_equal(ordered[2], [90, 80])
    assert np.array_equal(ordered[3], [5, 90])


def test_rectify_label_detects_large_document():
    image = np.zeros((420, 640, 3), dtype=np.uint8)
    quad = np.array([[100, 80], [530, 60], [560, 350], [70, 370]], dtype=np.int32)
    cv2.fillConvexPoly(image, quad, (255, 255, 255))
    cv2.polylines(image, [quad], True, (120, 120, 120), 4)

    result = rectify_label(
        image,
        {"min_area_ratio": 0.20, "canny_low": 30, "canny_high": 120},
        width=500,
        height=300,
    )

    assert result.shape == (300, 500, 3)
    assert result.mean() > 220


def test_qr_anchor_maps_corners_to_recipe_position():
    image = np.zeros((500, 700, 3), dtype=np.uint8)
    source = np.array([[400, 150], [520, 140], [530, 270], [390, 280]], dtype=np.float32)
    cv2.fillConvexPoly(image, source.astype(np.int32), (255, 255, 255))

    result = rectify_from_qr_anchor(
        image,
        source,
        target_roi=[0.60, 0.30, 0.20, 0.20],
        width=600,
        height=600,
    )

    target = result[180:300, 360:480]
    assert result.shape == (600, 600, 3)
    assert target.mean() > 240
