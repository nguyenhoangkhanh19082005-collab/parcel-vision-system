import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from machine_vision.models import (
    ClassificationResult,
    DamageAssessment,
    Decision,
    FocusMetrics,
    InspectionResult,
    LogoAssessment,
    ParcelData,
)
from machine_vision.services.evidence import EvidenceWriter


def test_evidence_writer_saves_metadata_and_images():
    classification = ClassificationResult(
        decision=Decision.PASS,
        destination_bin="BIN_HCM",
        reason="test",
        parcel=ParcelData(
            qr_text="VN123456789",
            waybill_code="VN123456789",
            logo=LogoAssessment(True, True, score=0.9, threshold=0.55),
            damage=DamageAssessment(True, False, confidence=0.99),
        ),
    )
    image = np.full((80, 120, 3), 127, dtype=np.uint8)
    inspection = InspectionResult(
        classification=classification,
        focus=FocusMetrics(100.0, 200.0),
        original_frame=image,
        label_image=image,
        debug_images={"qr crop": image},
    )

    with TemporaryDirectory() as temporary:
        writer = EvidenceWriter(
            {
                "enabled": True,
                "directory": "captures",
                "save_full_frame": True,
                "save_label_image": True,
                "save_debug_images": True,
            },
            Path(temporary),
        )
        folder = writer.save(inspection)
        assert folder is not None
        assert (folder / "frame.jpg").exists()
        assert (folder / "label.jpg").exists()
        assert (folder / "qr_crop.png").exists()
        metadata = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        assert metadata["decision"] == "PASS"
        assert metadata["parcel"]["logo"]["present"] is True
        assert metadata["parcel"]["damage"]["damaged"] is False
