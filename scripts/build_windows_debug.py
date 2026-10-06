from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.__main__ import run

PROJECT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / "build" / "windows"


def add_data(source: Path, destination: str) -> str:
    return f"{source}{os.pathsep}{destination}"


def sanitize_dll_search_path() -> None:
    windows_directory = Path(os.environ.get("WINDIR", r"C:\Windows")).resolve()
    safe_entries = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        directory = Path(entry)
        try:
            contains_icu = (directory / "icuuc.dll").is_file()
            is_windows = directory.resolve().is_relative_to(windows_directory)
        except OSError:
            contains_icu = False
            is_windows = False
        if contains_icu and not is_windows:
            continue
        safe_entries.append(entry)
    os.environ["PATH"] = os.pathsep.join(safe_entries)


def main() -> None:
    sanitize_dll_search_path()
    qml_source = PROJECT / "src" / "machine_vision" / "ui" / "qml"
    run(
        [
            str(PROJECT / "src" / "machine_vision" / "app.py"),
            "--name=MachineVisionDebug",
            "--onedir",
            "--console",
            "--noconfirm",
            "--clean",
            f"--paths={PROJECT / 'src'}",
            f"--distpath={OUTPUT / 'debug-dist'}",
            f"--workpath={OUTPUT / 'debug-work'}",
            f"--specpath={OUTPUT}",
            f"--add-data={add_data(PROJECT / 'config', 'config')}",
            f"--add-data={add_data(PROJECT / 'assets', 'assets')}",
            f"--add-data={add_data(qml_source, 'machine_vision/ui/qml')}",
            "--hidden-import=zxingcpp",
        ]
    )


if __name__ == "__main__":
    main()
