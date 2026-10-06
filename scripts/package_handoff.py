"""Build privacy-aware, reproducible handoff archives without touching source data."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "exports"
VERSION = "2026-10-05"

SOURCE_FILES = (
    "README.md",
    "RESOURCES.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "config/default.yaml",
    "config/calibration/.gitkeep",
    "config/calibration/logo_calibration.json",
    "src/machine_vision/ui/qml/DigitalTwinView.qml",
    "assets/digital_twin/scene_manifest.json",
    "assets/logo/spx_template.png",
    "firmware/sketch_sep19a.ino",
    "hardware/esp32_conveyor_schematic.png",
)
SOURCE_DIRS = ("src", "tests", "scripts")
DOCS = (
    "docs/architecture.md",
    "docs/hmi_digital_twin.md",
    "docs/3d_asset_handoff.md",
    "docs/damage_commissioning.md",
    "docs/esp32_contract.md",
    "docs/windows_exe.md",
    "docs/team_upload_guide.md",
)
PRIVATE_FILES = (
    ("exports/assets/logo/spx_template.png", "assets/logo/spx_template.png"),
    ("exports/config/calibration/empty_bench.png", "config/calibration/empty_bench.png"),
    ("config/calibration/empty_belt.png", "config/calibration/empty_belt.png"),
)


def add_file(archive: zipfile.ZipFile, path: Path, member: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    archive.write(path, f"MachineVision/{member}")


def build() -> list[Path]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_zip = OUTPUT / f"MachineVision_Core_Source_{VERSION}.zip"
    private_zip = OUTPUT / f"MachineVision_Private_Calibration_{VERSION}.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for member in (*SOURCE_FILES, *DOCS):
            add_file(archive, ROOT / member, member)
        for directory in SOURCE_DIRS:
            for path in sorted((ROOT / directory).rglob("*.py")):
                if "__pycache__" not in path.parts:
                    add_file(archive, path, path.relative_to(ROOT).as_posix())
    calibration = ROOT / "exports/config/calibration/logo_calibration.json"
    if not calibration.is_file():
        return [source_zip]
    with zipfile.ZipFile(private_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(
            "MachineVision/PRIVATE_CALIBRATION_README.md",
            "# Hiệu chuẩn hiện trường — Drive riêng\n\n"
            "Giải nén gói này vào cùng thư mục MachineVision của Core Source. "
            "Các ảnh nền chỉ đúng với vị trí camera/đèn khi chụp; cần chụp lại khi đổi setup. "
            "Không upload ảnh nền vào GitHub công khai. Xem README.md và RESOURCES.md "
            "trong gói Core để chạy ứng dụng.\n",
        )
        for source, member in PRIVATE_FILES:
            if (ROOT / source).is_file():
                add_file(archive, ROOT / source, member)
        data = json.loads(calibration.read_text(encoding="utf-8"))
        data["template_path"] = "assets/logo/spx_template.png"
        archive.writestr(
            "MachineVision/config/calibration/logo_calibration.json",
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        )
    return [source_zip, private_zip]


if __name__ == "__main__":
    for result in build():
        print(result)
