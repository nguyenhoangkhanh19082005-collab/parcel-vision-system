"""Capture lossless 2K calibration images from a USB webcam.

The saved PNG contains the frame returned by OpenCV without crop, resize,
sharpening, thresholding, text overlays or other image processing. The webcam
may internally deliver MJPEG; OpenCV decodes it before this script receives it.

Controls
--------
1..6    Select the 15/20/25/30/35/40 cm dataset.
SPACE   Save one original frame and its JSON metadata.
B       Save a burst for the selected distance.
F       Toggle focus-peaking preview (preview only).
Q/ESC   Quit.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


BACKENDS = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "any": cv2.CAP_ANY,
}


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Capture unprocessed 2560x1440 frames at 15-40 cm."
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default="dshow",
        help="Windows capture backend",
    )
    parser.add_argument("--width", type=int, default=2560)
    parser.add_argument("--height", type=int, default=1440)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--fourcc", default="MJPG")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--burst-count", type=int, default=10)
    parser.add_argument("--burst-interval", type=float, default=0.20)
    parser.add_argument(
        "--orientation",
        choices=("landscape", "portrait"),
        default="landscape",
        help="A6 guide orientation in the preview",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "dataset" / "raw",
        help="Root output directory",
    )
    return parser.parse_args()


def open_camera(args: argparse.Namespace) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(args.camera, BACKENDS[args.backend])
    if not capture.isOpened():
        raise RuntimeError(
            f"Cannot open camera index {args.camera} with backend {args.backend}. "
            "Close other camera applications or try --backend msmf."
        )

    if len(args.fourcc) != 4:
        raise ValueError("--fourcc must contain exactly four characters")

    # FOURCC must be negotiated before resolution and FPS on many UVC webcams.
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.fourcc))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_FPS, args.fps)

    # Give exposure, white balance and autofocus time to settle.
    for _ in range(max(0, args.warmup)):
        capture.read()
    return capture


def camera_properties(capture: cv2.VideoCapture) -> dict[str, float | str]:
    value = int(capture.get(cv2.CAP_PROP_FOURCC))
    negotiated_fourcc = "".join(chr((value >> (8 * i)) & 0xFF) for i in range(4))
    return {
        "width": capture.get(cv2.CAP_PROP_FRAME_WIDTH),
        "height": capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
        "fps": capture.get(cv2.CAP_PROP_FPS),
        "fourcc": negotiated_fourcc,
        "autofocus": capture.get(cv2.CAP_PROP_AUTOFOCUS),
        "focus": capture.get(cv2.CAP_PROP_FOCUS),
        "exposure": capture.get(cv2.CAP_PROP_EXPOSURE),
        "gain": capture.get(cv2.CAP_PROP_GAIN),
    }


def focus_metrics(frame: np.ndarray) -> tuple[float, float, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    laplacian = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(sx * sx + sy * sy))
    highlight_ratio = float(np.count_nonzero(gray >= 250) / gray.size)
    return laplacian, tenengrad, highlight_ratio


def focus_peaking(frame: np.ndarray, threshold: float = 80.0) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(sx, sy)
    output = frame.copy()
    output[magnitude > threshold] = (0, 0, 255)
    return output


def draw_a6_guide(frame: np.ndarray, orientation: str) -> None:
    """Draw a centered A6 aspect-ratio guide on a preview frame only."""
    height, width = frame.shape[:2]
    # A6 is 105 x 148 mm. Use 70% of preview height as a visual guide.
    long_side, short_side = 148.0, 105.0
    if orientation == "landscape":
        guide_height = int(height * 0.70)
        guide_width = int(guide_height * long_side / short_side)
    else:
        guide_height = int(height * 0.78)
        guide_width = int(guide_height * short_side / long_side)
    if guide_width > int(width * 0.88):
        scale = (width * 0.88) / guide_width
        guide_width = int(guide_width * scale)
        guide_height = int(guide_height * scale)
    x1 = (width - guide_width) // 2
    y1 = (height - guide_height) // 2
    cv2.rectangle(frame, (x1, y1), (x1 + guide_width, y1 + guide_height), (40, 220, 150), 3)
    cv2.putText(
        frame,
        "A6 GUIDE 105 x 148 mm",
        (x1, max(35, y1 - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (40, 220, 150),
        2,
        cv2.LINE_AA,
    )


def save_frame(
    frame: np.ndarray,
    output_root: Path,
    distance_cm: int,
    sequence: int,
    properties: dict[str, float | str],
) -> Path:
    folder = output_root / f"{distance_cm}cm"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stem = f"stafor_{distance_cm}cm_{now.strftime('%Y%m%dT%H%M%S.%fZ')}_{sequence:03d}"
    image_path = folder / f"{stem}.png"
    metadata_path = folder / f"{stem}.json"

    # PNG is lossless. Compression level 1 is fast and does not change pixels.
    if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
        raise RuntimeError(f"Failed to save {image_path}")

    laplacian, tenengrad, highlight_ratio = focus_metrics(frame)
    metadata = {
        "captured_at_utc": now.isoformat(),
        "camera_name": "Stafor 2K",
        "camera_index": properties.get("camera_index"),
        "distance_cm": distance_cm,
        "label_format": "A6",
        "saved_width": int(frame.shape[1]),
        "saved_height": int(frame.shape[0]),
        "processing": "none; original OpenCV frame saved as lossless PNG",
        "camera_properties": properties,
        "quality_metrics": {
            "laplacian_variance": laplacian,
            "tenengrad": tenengrad,
            "highlight_ratio": highlight_ratio,
        },
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path


def main() -> int:
    args = parse_args()
    args.output = args.output.resolve()
    capture = open_camera(args)
    properties = camera_properties(capture)
    properties["camera_index"] = args.camera

    actual_size = (int(properties["width"]), int(properties["height"]))
    requested_size = (args.width, args.height)
    print("Requested:", requested_size, f"@ {args.fps:g} FPS, {args.fourcc}")
    print("Negotiated:", properties)
    print("Output:", args.output)
    if actual_size != requested_size:
        print(
            "WARNING: webcam did not negotiate the requested 2K resolution. "
            "Try --backend msmf, another USB port, or inspect supported camera modes."
        )

    distance_cm = 15
    sequence = {15: 0, 20: 0, 25: 0, 30: 0, 35: 0, 40: 0}
    show_peaking = False
    last_saved = ""
    window_name = "Stafor 2K Calibration Capture"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    try:
        while True:
            ok, original = capture.read()
            if not ok or original is None:
                raise RuntimeError("The webcam returned an empty frame")

            # Everything below is drawn only on this preview copy.
            preview = focus_peaking(original) if show_peaking else original.copy()
            draw_a6_guide(preview, args.orientation)
            analysis_scale = min(1.0, 1280.0 / original.shape[1])
            analysis = cv2.resize(
                original,
                None,
                fx=analysis_scale,
                fy=analysis_scale,
                interpolation=cv2.INTER_AREA,
            )
            laplacian, tenengrad, highlight_ratio = focus_metrics(analysis)
            lines = [
                f"Dataset: {distance_cm} cm | Saved: {sequence[distance_cm]}",
                f"Frame: {original.shape[1]}x{original.shape[0]} | L={laplacian:.1f} "
                f"T={tenengrad:.1f} Glare={highlight_ratio:.3f}",
                "[1]15 [2]20 [3]25 [4]30 [5]35 [6]40 cm  [SPACE]Save [B]Burst [Q]Quit",
            ]
            for row, text in enumerate(lines):
                y = 38 + row * 34
                cv2.putText(preview, text, (25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 5)
                cv2.putText(preview, text, (25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
            if last_saved:
                cv2.putText(
                    preview,
                    last_saved,
                    (25, preview.shape[0] - 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (40, 220, 150),
                    2,
                    cv2.LINE_AA,
                )

            # Preview may be scaled by the OS/window; the saved frame is never resized.
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                break
            if key == ord("1"):
                distance_cm = 15
                last_saved = "Selected 15 cm. Measure from lens/front glass to label surface."
            elif key == ord("2"):
                distance_cm = 20
                last_saved = "Selected 20 cm. Measure from lens/front glass to label surface."
            elif key == ord("3"):
                distance_cm = 25
                last_saved = "Selected 25 cm. Measure from lens/front glass to label surface."
            elif key == ord("4"):
                distance_cm = 30
                last_saved = "Selected 30 cm. Measure from lens/front glass to label surface."
            elif key == ord("5"):
                distance_cm = 35
                last_saved = "Selected 35 cm. Measure from lens/front glass to label surface."
            elif key == ord("6"):
                distance_cm = 40
                last_saved = "Selected 40 cm. Measure from lens/front glass to label surface."
            elif key == ord("f"):
                show_peaking = not show_peaking
            elif key == 32:  # SPACE
                sequence[distance_cm] += 1
                path = save_frame(
                    original.copy(), args.output, distance_cm, sequence[distance_cm], properties
                )
                last_saved = f"Saved original frame: {path.name}"
                print(last_saved)
            elif key == ord("b"):
                for _ in range(max(1, args.burst_count)):
                    ok, burst_frame = capture.read()
                    if not ok or burst_frame is None:
                        raise RuntimeError("The webcam returned an empty burst frame")
                    sequence[distance_cm] += 1
                    path = save_frame(
                        burst_frame.copy(),
                        args.output,
                        distance_cm,
                        sequence[distance_cm],
                        properties,
                    )
                    print(f"Saved burst frame: {path.name}")
                    time.sleep(max(0.0, args.burst_interval))
                last_saved = f"Saved {args.burst_count} frames to {distance_cm}cm"
    finally:
        capture.release()
        cv2.destroyAllWindows()

    print("Capture completed.")
    print(f"15 cm images: {sequence[15]}")
    print(f"20 cm images: {sequence[20]}")
    print(f"25 cm images: {sequence[25]}")
    print(f"30 cm images: {sequence[30]}")
    print(f"35 cm images: {sequence[35]}")
    print(f"40 cm images: {sequence[40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
