
from machine_vision import paths


def test_frozen_paths_use_bundle_and_executable_directories(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    executable = tmp_path / "portable" / "MachineVision.exe"
    bundle.mkdir()
    executable.parent.mkdir()
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.resource_root() == bundle.resolve()
    assert paths.runtime_root() == executable.parent.resolve()


def test_external_config_and_assets_override_bundle(monkeypatch, tmp_path):
    portable = tmp_path / "portable"
    config = portable / "config" / "default.yaml"
    (portable / "assets").mkdir(parents=True)
    config.parent.mkdir()
    config.write_text("station: {}", encoding="utf-8")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(portable / "MachineVision.exe"))

    assert paths.default_config_path() == config
    assert paths.asset_root(config) == portable.resolve()
