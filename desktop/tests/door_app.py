"""Starts the Python app for one Rust screen test (P3): the light app's signed-in window on a copy of the
test account, Material on the week of Monday 2 November 2026 with the shared fake clock (Thursday 19:00),
and the test door on `--door PATH`. Prints "door ready" once the door listens, then runs until the process
is stopped. Test-only: `python -m desktop.tests.door_app --door PATH --folder DIR`.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path

os.environ["FLEXWEEK_SILENT"] = "1"
os.environ["FONTCONFIG_FILE"] = str(Path(__file__).with_name("fontconfig.conf"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# As in the app and the Python suite: the collector runs on the window's thread only.
gc.disable()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--door", required=True)
    parser.add_argument("--folder", required=True)
    arguments = parser.parse_args(argv)

    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication

    from backend import clock as app_clock
    from backend.tests.fake_clock import CLOCK

    app_clock.use(CLOCK)
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication(["flexweek-test-door"])

    from desktop.tests.door import Door
    from desktop.tests.light_app import LightWindows
    from desktop.tests.material_support import show_material

    folder = Path(arguments.folder)
    windows = LightWindows(app, folder / "account", folder / "windows")
    window = windows.open((1280, 800))
    show_material(app, window)
    door = Door(window, arguments.door)
    print("door ready", flush=True)
    try:
        return app.exec()
    finally:
        del door
        windows.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
