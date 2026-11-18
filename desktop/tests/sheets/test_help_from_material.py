"""Help on the Widgets looks: its key list follows the two Settings switches. Material shows Help as its own
sheet (test_material_info_sheets.py)."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import settings
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.window_support import look_file, qapp, turn_on_letter_keys  # noqa: F401

# A sheet that does not close ends the test instead of hanging it.
GIVE_UP_MS = 2500


def _key(key: Qt.Key) -> None:
    """A key as the keyboard delivers it: to the widget that has the focus, or the sheet itself."""
    target = QApplication.focusWidget() or QApplication.activeModalWidget()
    QTest.keyClick(target, key)


def _with_help_open(qapp: QApplication, window: NativeWindow, after_opening) -> dict:
    """Open Help the way More does, run `after_opening(dialog, seen)` as soon as it is on screen and
    report what happened. `seen` holds "stuck" when the sheet was still up at the end."""
    seen: dict = {}
    waiting = QTimer()
    waiting.setInterval(25)
    deadline = QTimer()
    deadline.setSingleShot(True)

    def drive() -> None:
        dialog = QApplication.activeModalWidget()
        # A key goes to whichever window the system made active; a student's first key comes after that.
        # Two ticks in a row, so the sheet's own first focus has been given too.
        if "dialog" in seen or not (isinstance(dialog, settings.HelpDialog) and dialog.isActiveWindow()):
            seen["ticks"] = 0
            return
        seen["ticks"] = seen.get("ticks", 0) + 1
        if seen["ticks"] < 2:
            return
        waiting.stop()
        seen["dialog"] = dialog
        after_opening(dialog, seen)

    def give_up() -> None:
        waiting.stop()
        stuck = QApplication.activeModalWidget()
        if stuck is not None:
            seen["stuck"] = True
            stuck.reject()

    waiting.timeout.connect(drive)
    deadline.timeout.connect(give_up)
    waiting.start()
    deadline.start(GIVE_UP_MS)
    window._open_help()
    waiting.stop()
    deadline.stop()
    pump(qapp)
    return seen


def _spoken_keys(dialog: settings.HelpDialog) -> list[str]:
    return [row.accessibleName() for row in dialog.findChildren(QWidget, "helpKey")]


def test_help_in_the_widgets_looks_follows_its_two_switches(qapp: QApplication, window: NativeWindow) -> None:
    def rows() -> list[str]:
        seen: list[str] = []

        def read(dialog: settings.HelpDialog, _seen: dict) -> None:
            seen.extend(_spoken_keys(dialog))
            dialog.reject()

        _with_help_open(qapp, window, read)
        return seen

    by_default = rows()
    assert "1 to 5" in by_default and "D W M" not in by_default
    for letter in ("T", "J K", "C", "P", "Z", "F"):
        assert letter not in by_default, letter
    assert "Ctrl+Shift+F" in by_default and "F1" in by_default and "Ctrl+K" in by_default
    turn_on_letter_keys()
    with_letters = rows()
    for key in ("1 to 5", "T", "D W M", "J K", "C", "P", "Z", "F"):
        assert key in with_letters, key
