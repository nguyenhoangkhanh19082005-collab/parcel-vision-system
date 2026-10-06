from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from machine_vision.camera.opencv_camera import OpenCVCamera  # noqa: E402
from machine_vision.config import load_config  # noqa: E402
from machine_vision.imaging.enhancement import crop_fraction  # noqa: E402
from machine_vision.imaging.focus import assess_focus, focus_peaking  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT / "config" / "default.yaml"))
    parser.add_argument("--csv", default=str(PROJECT / "focus_samples.csv"))
    args = parser.parse_args()
    config = load_config(args.config).raw
    rows = []
    previous = None

    with OpenCVCamera(config["camera"]) as camera:
        print("Negotiated camera properties:", camera.negotiated_properties())
        print("SPACE: save sample, Q: quit")
        while True:
            frame = camera.read()
            label = crop_fraction(frame, config["label"]["roi"])
            metrics = assess_focus(label, previous)
            previous = label
            preview = focus_peaking(frame)
            cv2.putText(
                preview,
                f"L={metrics.laplacian:.1f} T={metrics.tenengrad:.1f} "
                f"M={metrics.motion:.1f} G={metrics.highlight_ratio:.3f}",
                (30, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (40, 230, 160),
                2,
            )
            cv2.imshow("Focus calibration", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == 32:
                label_text = input("Sample label [good/bad]: ").strip().lower()
                rows.append(
                    [label_text, metrics.laplacian, metrics.tenengrad,
                     metrics.motion, metrics.highlight_ratio]
                )
                print("Saved", rows[-1])

    cv2.destroyAllWindows()
    output = Path(args.csv)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label", "laplacian", "tenengrad", "motion", "highlight_ratio"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} samples to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

