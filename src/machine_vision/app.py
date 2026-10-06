from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from machine_vision.config import load_config
from machine_vision.paths import (
    asset_root,
    default_config_path,
    resource_root,
    runtime_root,
)
from machine_vision.readers.logo_reader import TemplateLogoDetector
from machine_vision.readers.qr_reader import QrReader
from machine_vision.repositories.shipments import (
    InMemoryShipmentRepository,
    SupabaseShipmentRepository,
)
from machine_vision.services.classifier import ParcelClassifier
from machine_vision.services.damage import PackageDamageDetector
from machine_vision.services.evidence import EvidenceWriter
from machine_vision.services.pipeline import VisionPipeline
from machine_vision.ui.main_window import MainWindow


def build_pipeline(
    config: dict,
    project_root: Path | None = None,
    writable_root: Path | None = None,
) -> tuple[VisionPipeline, str | None]:
    project_root = project_root or resource_root()
    writable_root = writable_root or runtime_root()
    warnings = []
    logo_detector = TemplateLogoDetector(config["logo"], project_root, writable_root)
    if logo_detector.template is None:
        warnings.append(f"Logo template not found: {logo_detector.template_path}")
    damage_detector = PackageDamageDetector(config["damage"], project_root, writable_root)
    if damage_detector.production_reference is None:
        warnings.append(f"Empty-belt reference not found: {damage_detector.reference_path}")

    db_cfg = config["supabase"]
    if db_cfg.get("enabled", False):
        repository = SupabaseShipmentRepository(db_cfg)
    else:
        repository = InMemoryShipmentRepository([])

    classifier = ParcelClassifier(config["classification"], repository)
    pipeline = VisionPipeline(
        config,
        QrReader(config["qr"]),
        logo_detector,
        damage_detector,
        classifier,
    )
    return pipeline, ". ".join(warnings) if warnings else None


def main() -> int:
    writable_root = runtime_root()
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(writable_root / ".env")
    except ImportError:
        # dotenv is installed by the database extra; normal environment variables still work.
        pass
    parser = argparse.ArgumentParser(description="Machine Vision parcel sorting station")
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Path to station YAML configuration",
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path).raw
    project_root = asset_root(config_path)

    app = QApplication(sys.argv)
    pipeline, warning = build_pipeline(config, project_root, writable_root)
    evidence = EvidenceWriter(config.get("audit", {}), writable_root)
    window = MainWindow(config, pipeline, evidence, project_root=project_root)
    window.show()
    if warning:
        QMessageBox.warning(window, "Commissioning required", warning)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
