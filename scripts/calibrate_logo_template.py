"""Crop a non-personal logo template from a rectified A6 commissioning image."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parents[1]


def parse_roi(value: str) -> list[float]:
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x,y,width,height")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT / "dataset" / "analysis" / "best_rectified_35cm.png",
    )
    parser.add_argument(
        "--output", type=Path, default=PROJECT / "assets" / "logo" / "spx_template.png"
    )
    parser.add_argument("--roi", type=parse_roi, default=[0.26, 0.13, 0.26, 0.115])
    args = parser.parse_args()
    image = cv2.imread(str(args.input))
    if image is None:
        raise FileNotFoundError(args.input)
    height, width = image.shape[:2]
    x, y, roi_width, roi_height = args.roi
    crop = image[
        int(y * height) : int((y + roi_height) * height),
        int(x * width) : int((x + roi_width) * width),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if crop.size == 0 or not cv2.imwrite(str(args.output), crop):
        raise RuntimeError(f"Unable to save logo template: {args.output}")
    print(f"Saved logo template: {args.output} ({crop.shape[1]}x{crop.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
