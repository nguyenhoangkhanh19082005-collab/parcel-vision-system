from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_MODEL_SUFFIXES = {".glb", ".gltf", ".obj"}


@dataclass(frozen=True)
class SceneAsset:
    """One replaceable 3D asset and its live-data node bindings."""

    asset_id: str
    label: str
    file: str
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    node_bindings: dict[str, str] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return bool(self.file.strip())

    def resolved_path(self, project_root: Path) -> Path | None:
        if not self.configured:
            return None
        candidate = (project_root / self.file).resolve()
        root = project_root.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"Asset '{self.asset_id}' points outside the project directory")
        if candidate.suffix.lower() not in SUPPORTED_MODEL_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_MODEL_SUFFIXES))
            raise ValueError(f"Asset '{self.asset_id}' must use one of: {supported}")
        return candidate

    def is_ready(self, project_root: Path) -> bool:
        path = self.resolved_path(project_root)
        return path is not None and path.is_file()


@dataclass(frozen=True)
class SceneManifest:
    version: int
    units: str
    up_axis: str
    assets: tuple[SceneAsset, ...]
    telemetry_bindings: dict[str, str] = field(default_factory=dict)

    def ready_count(self, project_root: Path) -> int:
        return sum(asset.is_ready(project_root) for asset in self.assets)

    @property
    def configured_count(self) -> int:
        return sum(asset.configured for asset in self.assets)

    def asset(self, asset_id: str) -> SceneAsset:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        raise KeyError(asset_id)


def _vector3(
    value: Any, name: str, default: tuple[float, float, float]
) -> tuple[float, float, float]:
    if value is None:
        return default
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    return tuple(float(component) for component in value)  # type: ignore[return-value]


def load_scene_manifest(path: Path, project_root: Path) -> SceneManifest:
    """Load and validate the trusted, project-local Digital Twin manifest."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("version", 0)) != 1:
        raise ValueError("Only Digital Twin manifest version 1 is supported")

    units = str(data.get("units", "meters")).lower()
    if units != "meters":
        raise ValueError("Digital Twin assets must use meters")
    up_axis = str(data.get("upAxis", "Y")).upper()
    if up_axis not in {"Y", "Z"}:
        raise ValueError("upAxis must be Y or Z")

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise TypeError("assets must be a list")
    seen: set[str] = set()
    assets: list[SceneAsset] = []
    for item in raw_assets:
        asset_id = str(item["id"])
        if asset_id in seen:
            raise ValueError(f"Duplicate asset id: {asset_id}")
        seen.add(asset_id)
        asset = SceneAsset(
            asset_id=asset_id,
            label=str(item.get("label", asset_id)),
            file=str(item.get("file", "")),
            translation=_vector3(item.get("translation"), "translation", (0.0, 0.0, 0.0)),
            rotation=_vector3(item.get("rotation"), "rotation", (0.0, 0.0, 0.0)),
            scale=_vector3(item.get("scale"), "scale", (1.0, 1.0, 1.0)),
            node_bindings={str(k): str(v) for k, v in item.get("nodeBindings", {}).items()},
        )
        asset.resolved_path(project_root)
        assets.append(asset)

    return SceneManifest(
        version=1,
        units=units,
        up_axis=up_axis,
        assets=tuple(assets),
        telemetry_bindings={
            str(k): str(v) for k, v in data.get("telemetryBindings", {}).items()
        },
    )
