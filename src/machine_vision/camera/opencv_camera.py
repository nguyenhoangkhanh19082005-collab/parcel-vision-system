from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np


class CameraError(RuntimeError):
    pass


class OpenCVCamera:
    """UVC camera adapter with explicit read-back of negotiated properties."""

    BACKENDS = {
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "any": cv2.CAP_ANY,
    }

    def __init__(self, settings: dict):
        self.settings = settings
        backend = self.BACKENDS.get(str(settings.get("backend", "dshow")).lower(), cv2.CAP_ANY)
        self.capture = cv2.VideoCapture(int(settings.get("index", 0)), backend)
        if not self.capture.isOpened():
            raise CameraError("Cannot open camera")
        self._configure()

    def _configure(self) -> None:
        fourcc = str(self.settings.get("fourcc", "MJPG"))
        if len(fourcc) == 4:
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.settings.get("width", 2560)))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.settings.get("height", 1440)))
        self.capture.set(cv2.CAP_PROP_FPS, float(self.settings.get("fps", 30)))

        autofocus = self.settings.get("autofocus")
        if autofocus is not None:
            self.capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if autofocus else 0)
        for key, prop in (
            ("focus", cv2.CAP_PROP_FOCUS),
            ("exposure", cv2.CAP_PROP_EXPOSURE),
            ("gain", cv2.CAP_PROP_GAIN),
        ):
            value = self.settings.get(key)
            if value is not None:
                self.capture.set(prop, float(value))

        for _ in range(int(self.settings.get("warmup_frames", 12))):
            self.capture.read()

    def negotiated_properties(self) -> dict[str, float]:
        return {
            "width": self.capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            "height": self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "fps": self.capture.get(cv2.CAP_PROP_FPS),
            "focus": self.capture.get(cv2.CAP_PROP_FOCUS),
            "exposure": self.capture.get(cv2.CAP_PROP_EXPOSURE),
            "gain": self.capture.get(cv2.CAP_PROP_GAIN),
        }

    def read(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise CameraError("Camera returned an empty frame")
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        while self.capture.isOpened():
            yield self.read()

    def close(self) -> None:
        self.capture.release()

    def __enter__(self) -> "OpenCVCamera":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

