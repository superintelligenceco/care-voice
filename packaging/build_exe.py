"""Build a standalone ``care-voice`` executable with PyInstaller.

Usage: ``python packaging/build_exe.py <asset-name>``, for example
``python packaging/build_exe.py care-voice-linux-arm64``. The executable lands
in ``dist/`` (with ``.exe`` appended on Windows).

Install the build tools first: ``pip install . pyinstaller tzdata``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_exe.py <asset-name>")
    PyInstaller.__main__.run(
        [
            str(ROOT / "src" / "care_voice" / "__main__.py"),
            "--onefile",
            "--console",
            "--noconfirm",
            "--clean",
            "--name",
            sys.argv[1],
            "--paths",
            str(ROOT / "src"),
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            "--specpath",
            str(ROOT / "build" / "pyinstaller"),
            # The bundled check-in script (data/default_script.yaml) and py.typed.
            "--collect-data",
            "care_voice",
            # Import every subpackage, including the lazily imported telephony and
            # dashboard modules.
            "--collect-submodules",
            "care_voice",
            # IANA time zones for systems without a zoneinfo database (Windows).
            "--collect-data",
            "tzdata",
        ]
    )


if __name__ == "__main__":
    main()
