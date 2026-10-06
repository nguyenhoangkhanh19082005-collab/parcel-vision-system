from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from machine_vision.models import InspectionResult


class EvidenceWriter:
    """Persist inspection evidence locally using atomic metadata replacement."""

    def __init__(self, settings: dict, project_root: Path):
        self.settings = settings
        directory = Path(str(settings.get("directory", "captures")))
        self.root = directory if directory.is_absolute() else project_root / directory

    def save(self, result: InspectionResult) -> Path | None:
        if not self.settings.get("enabled", True):
            return None
        now = datetime.now(UTC)
        inspection_id = f"{now.strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid4().hex[:8]}"
        folder = self.root / now.strftime("%Y-%m-%d") / inspection_id
        folder.mkdir(parents=True, exist_ok=False)

        if self.settings.get("save_full_frame", False):
            self._write_image(folder / "frame.jpg", result.original_frame)
        if self.settings.get("save_label_image", True):
            self._write_image(folder / "label.jpg", result.label_image)
        if self.settings.get("save_debug_images", True):
            for name, image in result.debug_images.items():
                self._write_image(folder / f"{self._safe_name(name)}.png", image)

        parcel = asdict(result.classification.parcel)
        metadata = {
            "inspection_id": inspection_id,
            "timestamp_utc": now.isoformat(),
            "decision": result.classification.decision.value,
            "destination_bin": result.classification.destination_bin,
            "reason": result.classification.reason,
            "focus": asdict(result.focus),
            "parcel": parcel,
            "database_record": result.classification.database_record,
        }
        temporary = folder / "result.json.tmp"
        final = folder / "result.json"
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, final)
        return folder

    @staticmethod
    def _write_image(path: Path, image: np.ndarray) -> None:
        temporary = path.with_name(path.stem + ".tmp" + path.suffix)
        if not cv2.imwrite(str(temporary), image):
            raise RuntimeError(f"Unable to write evidence image: {path}")
        os.replace(temporary, path)

    @staticmethod
    def _safe_name(value: str) -> str:
        return re_sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "image"


def re_sub(pattern: str, replacement: str, value: str) -> str:
    # Kept local so evidence filename sanitization has no dependency on label parsing.
    import re

    return re.sub(pattern, replacement, value)
