from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the directory containing bundled read-only application resources."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    """Return the writable directory next to the executable in frozen builds."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return resource_root()


def default_config_path() -> Path:
    """Prefer an editable external config, then fall back to the bundled copy."""

    external = runtime_root() / "config" / "default.yaml"
    if external.is_file():
        return external
    return resource_root() / "config" / "default.yaml"


def asset_root(config_path: Path | None = None) -> Path:
    """Prefer assets beside an external config, otherwise use bundled resources."""

    candidates: list[Path] = []
    if config_path is not None:
        candidates.append(config_path.resolve().parent.parent)
    candidates.append(runtime_root())
    for candidate in candidates:
        if (candidate / "assets").is_dir():
            return candidate
    return resource_root()
