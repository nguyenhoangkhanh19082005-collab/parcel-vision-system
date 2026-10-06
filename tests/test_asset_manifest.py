import json
from pathlib import Path

import pytest

from machine_vision.ui.asset_manifest import load_scene_manifest


def _write_manifest(path: Path, asset_file: str = "models/robot.glb") -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "units": "meters",
                "upAxis": "Y",
                "assets": [
                    {
                        "id": "robot",
                        "label": "Robot",
                        "file": asset_file,
                        "nodeBindings": {"joint1": "Robot/J1"},
                    }
                ],
                "telemetryBindings": {"robot.joints": "robot.joints_deg"},
            }
        ),
        encoding="utf-8",
    )


def test_scene_manifest_reports_asset_readiness(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "robot.glb").write_bytes(b"glTF")
    manifest_path = tmp_path / "scene_manifest.json"
    _write_manifest(manifest_path)

    manifest = load_scene_manifest(manifest_path, tmp_path)

    assert manifest.units == "meters"
    assert manifest.asset("robot").node_bindings["joint1"] == "Robot/J1"
    assert manifest.ready_count(tmp_path) == 1


def test_scene_manifest_rejects_asset_outside_project(tmp_path):
    manifest_path = tmp_path / "scene_manifest.json"
    _write_manifest(manifest_path, "../robot.glb")

    with pytest.raises(ValueError, match="outside"):
        load_scene_manifest(manifest_path, tmp_path)


def test_scene_manifest_rejects_unsupported_model_format(tmp_path):
    manifest_path = tmp_path / "scene_manifest.json"
    _write_manifest(manifest_path, "models/robot.fbx")

    with pytest.raises(ValueError, match="must use"):
        load_scene_manifest(manifest_path, tmp_path)
