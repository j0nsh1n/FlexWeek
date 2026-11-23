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
# Every door has a home of its own (the Rust Door sets HOME to its folder), as every Python test worker does,
# so the look and week-start files Qt's test paths keep never pass from one test to the next.
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

    from desktop.tests.door import SlotErrors

    # Recorded from the start, so an error raised while the window is made is reported too.
    slot_errors = SlotErrors()

    from backend import clock as app_clock
    from backend.tests.fake_clock import CLOCK

    app_clock.use(CLOCK)
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication(["flexweek-test-door"])

    from PySide6.QtGui import QDesktopServices

    from desktop.native import cpu_drawing, spotify
    from desktop.tests.door import Door
    from desktop.tests.light_app import LightWindows
    from desktop.tests.material_support import show_material

    # As the Python suite's guards do (desktop/tests/conftest.py): nothing reaches this computer's own apps
    # (Spotify over the session bus, links in the browser), and a graphics failure never starts a new copy.
    spotify.system_remote = spotify.NoRemote
    QDesktopServices.openUrl = staticmethod(lambda _url: False)  # type: ignore[method-assign]
    cpu_drawing.start_new_copy = lambda *, cpu: None  # type: ignore[assignment]

    folder = Path(arguments.folder)
    windows = LightWindows(app, folder / "account", folder / "windows")
    window = windows.open((1280, 800))
    show_material(app, window)
    door = Door(window, arguments.door, slot_errors)
    print("door ready", flush=True)
    try:
        return app.exec()
    finally:
        del door
        windows.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
