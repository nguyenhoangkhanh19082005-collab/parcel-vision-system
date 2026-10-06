from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class Decision(str, Enum):
    PASS = "PASS"
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class FocusMetrics:
    laplacian: float
    tenengrad: float
    motion: float = 0.0
    highlight_ratio: float = 0.0


@dataclass(frozen=True)
class PackageDetection:
    """Target parcel selected from the QR attached to its shipping label."""

    bbox: tuple[int, int, int, int]
    label_bbox: tuple[int, int, int, int]
    confidence: float
    method: str = "qr_anchor"
    qr_corners: np.ndarray | None = None


@dataclass(frozen=True)
class LogoAssessment:
    calibrated: bool
    present: bool | None
    score: float = 0.0
    threshold: float = 0.0
    bbox: tuple[int, int, int, int] | None = None
    reason: str = ""


@dataclass(frozen=True)
class DamageAssessment:
    calibrated: bool
    damaged: bool | None
    damage_types: tuple[str, ...] = ()
    confidence: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)
    bbox: tuple[int, int, int, int] | None = None
    reason: str = ""


@dataclass
class ParcelData:
    qr_text: str | None = None
    waybill_code: str | None = None
    logo: LogoAssessment | None = None
    damage: DamageAssessment | None = None


@dataclass
class ClassificationResult:
    decision: Decision
    destination_bin: str
    reason: str
    parcel: ParcelData
    database_record: dict[str, Any] | None = None


@dataclass
class InspectionResult:
    classification: ClassificationResult
    focus: FocusMetrics
    original_frame: np.ndarray
    label_image: np.ndarray
    debug_images: dict[str, np.ndarray] = field(default_factory=dict)
