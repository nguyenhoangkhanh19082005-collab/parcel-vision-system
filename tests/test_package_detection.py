import cv2
import numpy as np

from machine_vision.services.package_detection import QrAnchoredPackageDetector


def test_qr_anchor_selects_parcel_and_expands_to_carton_edges():
    frame = np.full((600, 900, 3), 238, dtype=np.uint8)
    cv2.rectangle(frame, (150, 110), (760, 530), (125, 155, 180), -1)
    cv2.rectangle(frame, (300, 120), (600, 520), (245, 245, 245), -1)
    qr_corners = np.array(
        [[510, 336], [570, 336], [570, 416], [510, 416]], dtype=np.float32
    )
    detector = QrAnchoredPackageDetector(
        {
            "min_edge_projection": 8,
            "relative_edge_projection": 0.20,
            "max_side_expansion": 1.2,
        },
        {"rectification": {"qr_target_roi": [0.70, 0.54, 0.20, 0.20]}},
    )

    result = detector.detect(frame, qr_corners)

    assert result is not None
    x, y, width, height = result.bbox
    assert x <= 155
    assert x + width >= 755
    assert y <= 125
    assert y + height >= 515
    assert result.confidence >= 0.9
