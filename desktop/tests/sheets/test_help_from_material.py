"""Help opened from Material's More menu: the keyboard works in it (Esc closes it, Tab reaches Close, Space
presses it), Material's own keys wait behind it, the keyboard goes back to the Material window when it
closes, and its key list names the keys Material answers to. How Close looks with focus on it is a picture."""

# ruff: noqa: F811
from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import settings
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, show_material
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401

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


def test_escape_closes_help_opened_from_material(qapp: QApplication, window: NativeWindow) -> None:
    show_material(qapp, window)
    seen = _with_help_open(qapp, window, lambda _dialog, _seen: _key(Qt.Key.Key_Escape))
    assert isinstance(seen["dialog"], settings.HelpDialog)
    assert "stuck" not in seen, "Esc closed Help"


def test_tab_reaches_close_and_space_presses_it(qapp: QApplication, window: NativeWindow) -> None:
    show_material(qapp, window)

    def tab_then_space(_dialog: QWidget, seen: dict) -> None:
        _key(Qt.Key.Key_Tab)
        focus = QApplication.focusWidget()
        seen["focus"] = focus.objectName() if focus is not None else None
        _key(Qt.Key.Key_Space)

    seen = _with_help_open(qapp, window, tab_then_space)
    assert seen["focus"] == "sheetClose", "the first Tab lands on Close"
    assert "stuck" not in seen, "Space on Close closed Help"


def test_the_keyboard_goes_back_to_the_material_window_when_help_closes(
    qapp: QApplication, window: NativeWindow
) -> None:
    show_material(qapp, window)
    seen = _with_help_open(qapp, window, lambda _dialog, _seen: _key(Qt.Key.Key_Escape))
    assert "stuck" not in seen
    quick = window._material_page._quick
    wait_until(qapp, lambda: QApplication.focusWidget() is quick, what="the keyboard to come back")
    assert QApplication.activeWindow() is window
    # On the Week it goes to the Week's own place in the rail, as after Material's own sheets.
    item = quick.quickWindow().activeFocusItem()
    assert item is not None and item.objectName() == "navWeek"


def test_materials_keys_do_nothing_behind_help(qapp: QApplication, window: NativeWindow) -> None:
    show_material(qapp, window)
    bridge = window._material_page.bridge
    assert bridge.property("shortcuts") is True
    before = bridge.property("screen")

    def press_three(dialog: QWidget, seen: dict) -> None:
        _key(Qt.Key.Key_3)
        pump(qapp)
        seen["screen"] = bridge.property("screen")
        dialog.reject()

    seen = _with_help_open(qapp, window, press_three)
    assert seen["screen"] == before, "3 did not change the screen behind Help"


def _spoken_keys(dialog: settings.HelpDialog) -> list[str]:
    return [row.accessibleName() for row in dialog.findChildren(QWidget, "helpKey")]


def _help_in_material(qapp: QApplication, window: NativeWindow, **material: bool) -> list[str]:
    """The key rows Help shows from Material when the look file holds `material`."""
    look_file().write_text(json.dumps({"material": material}))
    show_material(qapp, window)
    window._material_page.publish()
    pump(qapp)
    rows: list[str] = []

    def read(dialog: settings.HelpDialog, _seen: dict) -> None:
        rows.extend(_spoken_keys(dialog))
        dialog.reject()

    _with_help_open(qapp, window, read)
    return rows


def test_help_in_material_lists_the_number_keys_by_default_and_no_letter_keys(
    qapp: QApplication, window: NativeWindow
) -> None:
    rows = _help_in_material(qapp, window)
    assert "1 to 5" in rows
    assert "D W M" not in rows
    for letter in ("P", "Z", "F"):
        assert letter not in rows, letter
    assert "Ctrl+Z" in rows and "Ctrl+Y or Ctrl+Shift+Z" in rows and "Ctrl+S" in rows
    # Keys the Widgets looks answer to and Material does not.
    for key in ("T", "B or Esc", "F1", "Ctrl+N", "Ctrl+K", "Delete"):
        assert key not in rows, key
    # Ctrl+Shift+L is switched off in Material, and Esc does not put a held card back there.
    for key in ("Ctrl+Shift+L", "Esc while dragging"):
        assert key not in rows, key
    assert "Ctrl+= - 0" in rows and "Ctrl and the mouse wheel" in rows


def test_help_in_material_lists_the_letter_keys_only_when_their_switch_is_on(
    qapp: QApplication, window: NativeWindow
) -> None:
    rows = _help_in_material(qapp, window, letters=True)
    for letter in ("P", "Z", "F"):
        assert letter in rows, letter


def test_help_in_material_leaves_out_the_number_keys_when_their_switch_is_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    rows = _help_in_material(qapp, window, shortcuts=False)
    assert "1 to 5" not in rows
    assert "D W M" not in rows


def test_help_in_the_widgets_looks_keeps_its_list(qapp: QApplication, window: NativeWindow) -> None:
    seen: list[str] = []

    def read(dialog: settings.HelpDialog, _seen: dict) -> None:
        seen.extend(_spoken_keys(dialog))
        dialog.reject()

    _with_help_open(qapp, window, read)
    assert "D W M" in seen and "1 to 5" not in seen
    assert [row for row in seen if row in ("P", "Z")] == []
