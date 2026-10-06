from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from machine_vision.models import PackageDetection
from machine_vision.services.damage import PackageDamageDetector


def make_detector(root: Path, background: np.ndarray) -> PackageDamageDetector:
    cv2.imwrite(str(root / "empty.png"), background)
    return PackageDamageDetector(
        {
            "background_path": "empty.png",
            "roi": [0, 0, 1, 1],
            "difference_threshold": 10,
            "blur_kernel": 5,
            "morphology_kernel": 5,
            "min_package_area_ratio": 0.05,
            "min_rectangularity": 0.82,
            "min_solidity": 0.95,
            "approx_epsilon_ratio": 0.02,
            "max_vertices": 8,
        },
        root,
    )


def test_rectangular_package_passes_shape_gates():
    background = np.full((300, 400, 3), 255, dtype=np.uint8)
    frame = background.copy()
    cv2.rectangle(frame, (70, 60), (330, 250), (100, 100, 100), -1)

    with TemporaryDirectory() as temporary:
        assessment, _ = make_detector(Path(temporary), background).inspect(frame)

    assert assessment.calibrated is True
    assert assessment.damaged is False


def test_concave_package_is_classified_as_damage():
    background = np.full((300, 400, 3), 255, dtype=np.uint8)
    frame = background.copy()
    contour = np.array(
        [[70, 60], [330, 60], [330, 115], [245, 155], [330, 190], [330, 250], [70, 250]],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [contour], (100, 100, 100))

    with TemporaryDirectory() as temporary:
        assessment, _ = make_detector(Path(temporary), background).inspect(frame)

    assert assessment.calibrated is True
    assert assessment.damaged is True
    assert "dent_or_edge_tear" in assessment.damage_types


def test_clipped_package_requires_manual_review():
    background = np.full((300, 400, 3), 255, dtype=np.uint8)
    frame = background.copy()
    cv2.rectangle(frame, (0, 60), (330, 250), (100, 100, 100), -1)

    with TemporaryDirectory() as temporary:
        assessment, _ = make_detector(Path(temporary), background).inspect(frame)

    assert assessment.calibrated is True
    assert assessment.damaged is None
    assert "full package outline" in assessment.reason.lower()


def test_internal_hole_is_classified_as_puncture():
    background = np.full((300, 400, 3), 255, dtype=np.uint8)
    frame = background.copy()
    cv2.rectangle(frame, (70, 60), (330, 250), (100, 100, 100), -1)
    cv2.circle(frame, (280, 105), 16, (255, 255, 255), -1)

    with TemporaryDirectory() as temporary:
        assessment, debug = make_detector(Path(temporary), background).inspect(frame)

    assert assessment.damaged is True
    assert "hole_or_puncture" in assessment.damage_types
    assert assessment.metrics["holes"] >= 1
    assert "damage_holes" in debug


def test_bench_reference_can_be_captured_and_reused():
    frame = np.full((120, 160, 3), 180, dtype=np.uint8)
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        detector = PackageDamageDetector(
            {
                "background_path": "missing-production.png",
                "bench_background_path": "calibration/empty_bench.png",
            },
            root,
            root,
        )
        detector.set_bench_mode(True)
        assert detector.reference_ready() is False

        saved = detector.save_bench_reference(frame)

        assert saved.is_file()
        assert detector.reference_ready() is True


def test_qr_selected_package_surface_hole_is_detected_and_boxed():
    background = np.full((400, 600, 3), 245, dtype=np.uint8)
    frame = background.copy()
    cv2.rectangle(frame, (70, 60), (530, 340), (125, 155, 180), -1)
    cv2.rectangle(frame, (180, 75), (420, 330), (235, 235, 235), -1)
    cv2.circle(frame, (485, 155), 15, (15, 15, 15), -1)
    package = PackageDetection(
        bbox=(70, 60, 460, 280),
        label_bbox=(180, 75, 240, 255),
        confidence=0.94,
    )

    with TemporaryDirectory() as temporary:
        assessment, debug = make_detector(Path(temporary), background).inspect(
            frame, package
        )

    assert assessment.damaged is True
    assert "hole_or_puncture" in assessment.damage_types
    assert assessment.metrics["surface_holes"] >= 1
    assert debug["damage_overlay"].shape == frame.shape
    assert "surface_hole_mask" in debug
