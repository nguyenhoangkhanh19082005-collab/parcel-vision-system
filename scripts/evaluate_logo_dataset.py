"""Measure template-logo scores on rectified commissioning images."""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import cv2
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from machine_vision.imaging.enhancement import crop_fraction
from machine_vision.imaging.perspective import rectify_from_qr_anchor
from machine_vision.readers.logo_reader import TemplateLogoDetector
from machine_vision.readers.qr_reader import QrReader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("distances", nargs="*", default=["30cm", "35cm", "40cm"])
    args = parser.parse_args()
    config = yaml.safe_load((PROJECT / "config" / "default.yaml").read_text(encoding="utf-8"))
    detector = TemplateLogoDetector(config["logo"], PROJECT)
    qr_reader = QrReader(config["qr"])
    label_config = config["label"]
    rectification = label_config["rectification"]
    for raw_distance in args.distances:
        distance = raw_distance if raw_distance.endswith("cm") else f"{raw_distance}cm"
        scores = []
        detected = 0
        files = sorted((PROJECT / "dataset" / "raw" / distance).glob("*.png"))
        for path in files:
            frame = cv2.imread(str(path))
            if frame is None:
                continue
            label = crop_fraction(frame, label_config["roi"])
            qr = qr_reader.read(label)
            anchor = label
            if qr is None or qr.corners is None:
                qr = qr_reader.read(frame)
                anchor = frame
            if qr is None or qr.corners is None:
                continue
            rectified = rectify_from_qr_anchor(
                anchor,
                qr.corners,
                rectification["qr_target_roi"],
                int(label_config["rectify_width"]),
                int(label_config["rectify_height"]),
            )
            assessment, _ = detector.detect(rectified)
            scores.append(assessment.score)
            detected += int(assessment.present is True)
        if not scores:
            print(f"{distance}: no evaluable images")
            continue
        print(
            f"{distance}: {detected}/{len(scores)} detected, "
            f"score min/median/max={min(scores):.3f}/"
            f"{statistics.median(scores):.3f}/{max(scores):.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
