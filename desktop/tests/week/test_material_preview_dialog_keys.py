"""The paste preview that Duplicate and Ctrl+V open over Material is a Widgets dialog. Its keys are its own:
Esc closes it and duplicates nothing, and a number key does not change the Material screen behind it. The
keyboard goes back to the Material window once it is closed (as after Help)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.widgets import PreviewDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheets import bridge  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.test_material_block_menu_more import (  # noqa: E402
    choose_by_keyboard,
    count,
    on_screen,
    open_menu,
    quick_of,
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

# A preview that does not close ends the test instead of hanging it.
GIVE_UP_MS = 2500


def _with_preview_open(qapp: QApplication, start, after_opening) -> dict:
    """Run `start()`, which opens the preview, and call `after_opening(dialog, seen)` once it is on screen
    and active. `seen["stuck"]` is set when the preview was still up at the end."""
    seen: dict = {}
    waiting = QTimer()
    waiting.setInterval(25)
    deadline = QTimer()
    deadline.setSingleShot(True)

    def drive() -> None:
        dialog = QApplication.activeModalWidget()
        if "dialog" in seen or not (isinstance(dialog, PreviewDialog) and dialog.isActiveWindow()):
            seen["ticks"] = 0
            return
        # Two ticks in a row, so the preview's own first focus has been given too.
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
    start()
    waiting.stop()
    deadline.stop()
    pump(qapp)
    return seen


def _press(key: Qt.Key) -> None:
    target = QApplication.focusWidget() or QApplication.activeModalWidget()
    QTest.keyClick(target, key)


def _duplicate(qapp: QApplication, window: NativeWindow, screen: str):
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10")
    return lambda: choose_by_keyboard(qapp, window, menu, "Duplicate")


def _paste(qapp: QApplication, window: NativeWindow, screen: str):
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10")
    choose_by_keyboard(qapp, window, menu, "Copy")
    return lambda: QTest.keyClick(quick_of(window), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_escape_closes_the_preview_and_adds_nothing(
    qapp: QApplication, window: NativeWindow, screen: str, opened_by
) -> None:
    start = opened_by(qapp, window, screen)
    seen = _with_preview_open(qapp, start, lambda _dialog, _seen: _press(Qt.Key.Key_Escape))
    assert isinstance(seen["dialog"], PreviewDialog)
    assert "stuck" not in seen, "Esc closed the preview"
    settled(qapp, window)
    assert count(window, "Club") == 1


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_a_number_key_does_not_change_the_screen_behind_the_preview(
    qapp: QApplication, window: NativeWindow, screen: str, opened_by
) -> None:
    start = opened_by(qapp, window, screen)
    before = bridge(window).property("screen")

    def press_three(dialog: PreviewDialog, seen: dict) -> None:
        _press(Qt.Key.Key_3)
        pump(qapp)
        seen["screen"] = bridge(window).property("screen")
        dialog.reject()

    seen = _with_preview_open(qapp, start, press_three)
    assert seen["screen"] == before, "3 did not change the screen behind the preview"
    assert before == screen


@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_the_keyboard_goes_back_to_the_material_window_when_the_preview_closes(
    qapp: QApplication, window: NativeWindow, opened_by
) -> None:
    start = opened_by(qapp, window, "week")
    seen = _with_preview_open(qapp, start, lambda _dialog, _seen: _press(Qt.Key.Key_Escape))
    assert "stuck" not in seen
    quick = quick_of(window)
    wait_until(qapp, lambda: QApplication.focusWidget() is quick, what="the keyboard to come back")
    item = quick.quickWindow().activeFocusItem()
    assert item is not None and item.objectName() == "navWeek"
    # Material's own keys work again.
    QTest.keyClick(quick, Qt.Key.Key_3)
    pump(qapp, 10)
    assert bridge(window).property("screen") == "month"
