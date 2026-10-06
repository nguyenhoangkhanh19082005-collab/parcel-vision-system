from machine_vision.models import (
    DamageAssessment,
    Decision,
    LogoAssessment,
    ParcelData,
)
from machine_vision.repositories.shipments import InMemoryShipmentRepository
from machine_vision.services.classifier import ParcelClassifier

SETTINGS = {
    "reject_bin": "REJECT",
    "unknown_bin": "MANUAL_REVIEW",
    "destination_field": "destination_bin",
    "require_qr": True,
    "require_waybill": True,
    "require_logo": True,
    "require_damage_check": True,
}


def valid_parcel(**changes) -> ParcelData:
    values = {
        "qr_text": "VN123456789",
        "waybill_code": "VN123456789",
        "logo": LogoAssessment(True, True, score=0.9, threshold=0.55),
        "damage": DamageAssessment(True, False, confidence=0.99),
    }
    values.update(changes)
    return ParcelData(**values)


def test_matching_waybill_passes_to_database_bin():
    repository = InMemoryShipmentRepository(
        [{"waybill_code": "VN123456789", "destination_bin": "BIN_HCM"}]
    )
    classifier = ParcelClassifier(SETTINGS, repository)
    parcel = valid_parcel()

    result = classifier.classify(parcel)

    assert result.decision is Decision.PASS
    assert result.destination_bin == "BIN_HCM"


def test_missing_qr_is_rejected():
    classifier = ParcelClassifier(SETTINGS, InMemoryShipmentRepository([]))
    parcel = valid_parcel(qr_text=None)

    result = classifier.classify(parcel)

    assert result.decision is Decision.REJECT
    assert "QR" in result.reason


def test_damaged_package_is_sent_to_defect_bin_before_database_lookup():
    classifier = ParcelClassifier(
        {**SETTINGS, "defect_bin": "DEFECT"}, InMemoryShipmentRepository([])
    )
    parcel = valid_parcel(
        damage=DamageAssessment(
            True,
            True,
            damage_types=("deformation",),
            confidence=0.9,
            reason="Package shape defect detected: deformation",
        )
    )

    result = classifier.classify(parcel)

    assert result.decision is Decision.REJECT
    assert result.destination_bin == "DEFECT"


def test_uncalibrated_damage_check_requires_manual_review():
    classifier = ParcelClassifier(SETTINGS, InMemoryShipmentRepository([]))

    result = classifier.classify(
        valid_parcel(damage=DamageAssessment(False, None, reason="Missing reference"))
    )

    assert result.decision is Decision.MANUAL_REVIEW
    assert "reference" in result.reason.lower()


def test_missing_expected_logo_is_rejected():
    classifier = ParcelClassifier(SETTINGS, InMemoryShipmentRepository([]))

    result = classifier.classify(
        valid_parcel(
            logo=LogoAssessment(
                True,
                False,
                score=0.03,
                threshold=0.15,
                reason="Expected logo was not detected",
            )
        )
    )

    assert result.decision is Decision.REJECT
    assert "logo" in result.reason.lower()


def test_local_test_mode_passes_without_database_record():
    classifier = ParcelClassifier(
        {**SETTINGS, "local_test_mode": True, "local_test_bin": "LOCAL_TEST"},
        InMemoryShipmentRepository([]),
    )

    result = classifier.classify(valid_parcel())

    assert result.decision is Decision.PASS
    assert result.destination_bin == "LOCAL_TEST"
    assert result.database_record is None
    assert "supabase" in result.reason.lower()
