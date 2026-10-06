"""Analyze all distance capture sets and generate a commissioning report."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from machine_vision.imaging.enhancement import crop_fraction  # noqa: E402
from machine_vision.imaging.focus import laplacian_variance, tenengrad  # noqa: E402
from machine_vision.imaging.perspective import rectify_from_qr_anchor  # noqa: E402
from machine_vision.readers.qr_reader import QrReader  # noqa: E402


LABEL_SEARCH_ROI = [0.14, 0.02, 0.60, 0.96]
QR_TARGET_ROI = [0.742857, 0.418919, 0.20, 0.141892]
CANONICAL_SIZE = (1050, 1480)
ZONES = {
    "label": [0.05, 0.04, 0.92, 0.72],
    "logo": [0.22, 0.12, 0.32, 0.15],
    "qr": [0.72, 0.40, 0.25, 0.18],
}


def median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def analyze_distance(folder: Path, output: Path) -> dict:
    reader = QrReader({"upscales": [2.0, 3.0], "try_inverted": True})
    images = sorted(folder.glob("*.png"))
    records = []
    best_score = -1.0
    best_rectified = None
    qr_values: set[str] = set()

    for path in images:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        search = crop_fraction(frame, LABEL_SEARCH_ROI)
        qr = reader.read(search)
        anchor_image = search
        if qr is None or qr.corners is None:
            qr = reader.read(frame)
            anchor_image = frame
        record = {"file": path.name, "qr_success": False, "zones": {}}
        if qr is not None:
            qr_values.add(qr.text)
        if qr is None or qr.corners is None:
            records.append(record)
            continue

        rectified = rectify_from_qr_anchor(
            anchor_image,
            qr.corners,
            QR_TARGET_ROI,
            CANONICAL_SIZE[0],
            CANONICAL_SIZE[1],
        )
        record["qr_success"] = True
        record["qr_text"] = qr.text
        for name, roi in ZONES.items():
            zone = crop_fraction(rectified, roi)
            record["zones"][name] = {
                "laplacian": laplacian_variance(zone),
                "tenengrad": tenengrad(zone),
            }
        score = record["zones"]["label"]["laplacian"]
        if score > best_score:
            best_score = score
            best_rectified = rectified
        records.append(record)

    if best_rectified is not None:
        cv2.imwrite(str(output / f"best_rectified_{folder.name}.png"), best_rectified)

    summary = {
        "distance": folder.name,
        "image_count": len(images),
        "qr_success_count": sum(bool(row["qr_success"]) for row in records),
        "qr_values": sorted(qr_values),
        "zones": {},
    }
    for zone in ZONES:
        available = [row["zones"][zone] for row in records if zone in row["zones"]]
        summary["zones"][zone] = {
            "median_laplacian": median([row["laplacian"] for row in available]),
            "median_tenengrad": median([row["tenengrad"] for row in available]),
        }
    return {"summary": summary, "frames": records}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=PROJECT / "dataset" / "raw")
    parser.add_argument("--output", type=Path, default=PROJECT / "dataset" / "analysis")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    reports = []
    folders = sorted(
        (folder for folder in args.input.glob("*cm") if folder.is_dir()),
        key=lambda folder: int(folder.name.removesuffix("cm")),
    )
    for folder in folders:
        reports.append(analyze_distance(folder, args.output))
    if not reports:
        raise RuntimeError(f"No capture folders found under {args.input}")

    ranked = sorted(
        reports,
        key=lambda item: (
            item["summary"]["qr_success_count"] / max(1, item["summary"]["image_count"]),
            item["summary"]["zones"]["label"]["median_laplacian"],
        ),
        reverse=True,
    )
    result = {
        "recommended_distance": ranked[0]["summary"]["distance"],
        "reason": "Highest QR success rate, then highest normalized label sharpness",
        "reports": reports,
    }
    path = args.output / "capture_report.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), **{r["summary"]["distance"]: r["summary"] for r in reports}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
