from pathlib import Path
from tempfile import TemporaryDirectory
import json

import cv2
import numpy as np

from machine_vision.readers.logo_reader import TemplateLogoDetector


def test_template_logo_detector_finds_expected_logo():
    template = np.full((50, 100, 3), 230, dtype=np.uint8)
    cv2.putText(template, "SPX", (4, 39), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    label = np.full((250, 400, 3), 230, dtype=np.uint8)
    label[80:130, 160:260] = template

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        cv2.imwrite(str(root / "logo.png"), template)
        detector = TemplateLogoDetector(
            {
                "template_path": "logo.png",
                "search_roi": [0, 0, 1, 1],
                "threshold": 0.10,
                "min_good_matches": 4,
                "min_inlier_ratio": 0.5,
            },
            root,
        )

        assessment, _ = detector.detect(label)

    assert assessment.calibrated is True
    assert assessment.present is True
    assert assessment.score >= 0.10


def test_template_logo_detector_rejects_blank_label():
    template = np.full((50, 100, 3), 230, dtype=np.uint8)
    cv2.putText(template, "SPX", (4, 39), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    blank = np.full((250, 400, 3), 230, dtype=np.uint8)

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        cv2.imwrite(str(root / "logo.png"), template)
        detector = TemplateLogoDetector(
            {"template_path": "logo.png", "search_roi": [0, 0, 1, 1]}, root
        )

        assessment, _ = detector.detect(blank)

    assert assessment.calibrated is True
    assert assessment.present is False


def test_operator_calibration_persists_template_and_search_roi():
    label = np.full((300, 500, 3), 235, dtype=np.uint8)
    cv2.rectangle(label, (90, 70), (280, 135), (20, 20, 20), 2)
    cv2.circle(label, (120, 102), 20, (20, 20, 20), 3)
    cv2.putText(
        label,
        "XPRESS",
        (145, 115),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (20, 20, 20),
        2,
    )

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        bundle = root / "bundle"
        runtime = root / "runtime"
        (bundle / "assets" / "logo").mkdir(parents=True)
        old_template = np.full((50, 100, 3), 220, dtype=np.uint8)
        cv2.putText(
            old_template,
            "OLD",
            (4, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
        )
        bundled_path = bundle / "assets" / "logo" / "spx_template.png"
        cv2.imwrite(str(bundled_path), old_template)
        settings = {
            "template_path": "assets/logo/spx_template.png",
            "calibration_path": "config/calibration/logo_calibration.json",
            "search_roi": [0.2, 0.1, 0.3, 0.2],
            "min_template_features": 4,
            "threshold": 0.05,
            "min_good_matches": 4,
            "min_inlier_ratio": 0.3,
        }
        detector = TemplateLogoDetector(settings, bundle, runtime)

        result = detector.calibrate(label, (85, 65, 205, 80))

        override = runtime / "assets" / "logo" / "spx_template.png"
        calibration = runtime / "config" / "calibration" / "logo_calibration.json"
        assert override.is_file()
        assert calibration.is_file()
        assert Path(str(result["template_path"])) == override
        assert int(result["sift_keypoints"]) >= 4
        assert result["backup_path"] is not None
        saved = json.loads(calibration.read_text(encoding="utf-8"))
        assert saved["search_roi"][2] > saved["template_roi"][2]

        reloaded = TemplateLogoDetector(settings, bundle, runtime)
        assert reloaded.template_path == override
        assert reloaded.search_roi == saved["search_roi"]
        assessment, _ = reloaded.detect(label)
        assert assessment.present is True
