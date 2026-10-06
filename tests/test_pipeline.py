import cv2
import numpy as np
import pytest

from machine_vision.models import DamageAssessment, Decision, FocusMetrics, LogoAssessment
from machine_vision.readers.qr_reader import QrReader
from machine_vision.repositories.shipments import InMemoryShipmentRepository
from machine_vision.services import pipeline as pipeline_module
from machine_vision.services.classifier import ParcelClassifier
from machine_vision.services.pipeline import FrameQualityError, VisionPipeline


class FakeLogoDetector:
    def detect(self, image):
        return LogoAssessment(True, True, score=0.9, threshold=0.55), image


class FakeDamageDetector:
    def inspect(self, _image, _package=None):
        return DamageAssessment(True, False, confidence=0.99), {}


def test_synthetic_pipeline_decodes_and_classifies():
    frame = np.full((1000, 1600, 3), 255, dtype=np.uint8)
    qr = cv2.QRCodeEncoder_create().encode("VN123456789")
    qr = cv2.resize(qr, (400, 400), interpolation=cv2.INTER_NEAREST)
    frame[30:430, 1120:1520] = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)

    config = {
        "acquisition": {
            "min_laplacian": 0,
            "min_tenengrad": 0,
            "motion_threshold": 999,
            "max_highlight_ratio": 1.0,
        },
        "label": {
            "roi": [0, 0, 1, 1],
            "qr_roi": [0.68, 0.0, 0.30, 0.48],
            "rectification": {"enabled": False},
        },
    }
    classification = {
        "reject_bin": "REJECT",
        "unknown_bin": "MANUAL_REVIEW",
        "destination_field": "destination_bin",
        "require_qr": True,
        "require_waybill": True,
        "require_logo": True,
        "require_damage_check": True,
    }
    repository = InMemoryShipmentRepository(
        [{"waybill_code": "VN123456789", "destination_bin": "BIN_HCM"}]
    )
    pipeline = VisionPipeline(
        config,
        QrReader({"upscale": 2.0, "try_inverted": True}),
        FakeLogoDetector(),
        FakeDamageDetector(),
        ParcelClassifier(classification, repository),
    )

    result = pipeline.inspect([frame, frame])

    assert result.classification.decision is Decision.PASS
    assert result.classification.destination_bin == "BIN_HCM"
    assert result.classification.parcel.qr_text == "VN123456789"
    assert result.classification.parcel.logo.present is True
    assert result.classification.parcel.damage.damaged is False


def test_bench_profile_relaxes_quality_gate(monkeypatch: pytest.MonkeyPatch):
    config = {
        "acquisition": {
            "stable_frames": 2,
            "min_laplacian": 12.5,
            "min_tenengrad": 1180.0,
            "motion_threshold": 3.5,
            "max_highlight_ratio": 0.03,
            "bench": {
                "stable_frames": 2,
                "min_laplacian": 3.0,
                "min_tenengrad": 450.0,
                "motion_threshold": 4.5,
                "max_highlight_ratio": 0.06,
            },
        },
        "label": {"roi": [0, 0, 1, 1]},
    }
    repository = InMemoryShipmentRepository([])
    pipeline = VisionPipeline(
        config,
        QrReader({}),
        FakeLogoDetector(),
        FakeDamageDetector(),
        ParcelClassifier(
            {
                "reject_bin": "REJECT",
                "unknown_bin": "MANUAL_REVIEW",
                "destination_field": "destination_bin",
                "require_qr": True,
            },
            repository,
        ),
    )
    measured = FocusMetrics(4.0, 593.0, motion=2.3, highlight_ratio=0.01)
    monkeypatch.setattr(pipeline_module, "assess_focus", lambda *_args: measured)
    frames = [np.zeros((40, 60, 3), dtype=np.uint8) for _ in range(3)]

    with pytest.raises(FrameQualityError, match="AUTO / BĂNG TẢI"):
        pipeline.choose_best_frame(frames)

    pipeline.set_bench_mode(True)
    selected, metrics = pipeline.choose_best_frame(frames)

    assert selected.shape == frames[0].shape
    assert metrics == measured
    assert pipeline.acquisition_settings()["min_laplacian"] == 3.0
