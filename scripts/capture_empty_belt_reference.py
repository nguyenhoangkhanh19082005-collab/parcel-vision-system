"""Capture an averaged empty-conveyor reference for package segmentation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from machine_vision.camera.opencv_camera import OpenCVCamera


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT / "config" / "default.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT / "config" / "calibration" / "empty_belt.png",
    )
    parser.add_argument("--frames", type=int, default=20)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    print("Remove every parcel from the conveyor. Capturing empty-belt reference...")
    samples = []
    with OpenCVCamera(config["camera"]) as camera:
        for _ in range(max(3, args.frames)):
            samples.append(camera.read().astype(np.float32))
    reference = np.median(np.stack(samples), axis=0).astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), reference):
        raise RuntimeError(f"Unable to save {args.output}")
    print(f"Saved empty-belt reference: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
