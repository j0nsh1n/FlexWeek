"""The paste preview that Duplicate and Ctrl+V open over Material is Material's own sheet. Esc closes it and
duplicates nothing, a number key does not change the Material screen behind it, and the keyboard goes back to
where it was once it is closed (as after Help)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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


def _press(window: NativeWindow, key: Qt.Key) -> None:
    QTest.keyClick(quick_of(window), key)


def _duplicate(qapp: QApplication, window: NativeWindow, screen: str):
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10")
    return lambda: choose_by_keyboard(qapp, window, menu, "Duplicate")


def _paste(qapp: QApplication, window: NativeWindow, screen: str):
    block = on_screen(qapp, window, screen, "Club")
    menu = open_menu(qapp, window, block, "shift-f10")
    choose_by_keyboard(qapp, window, menu, "Copy")
    return lambda: QTest.keyClick(quick_of(window), Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)


def _preview_open(qapp: QApplication, window: NativeWindow, start) -> None:
    start()
    wait_until(qapp, lambda: bridge(window).sheets.kind == "preview", what="the preview sheet")
    pump(qapp, 20)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_escape_closes_the_preview_and_adds_nothing(
    qapp: QApplication, window: NativeWindow, screen: str, opened_by
) -> None:
    _preview_open(qapp, window, opened_by(qapp, window, screen))
    _press(window, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: bridge(window).sheets.kind == "", what="Esc to close the preview")
    settled(qapp, window)
    assert count(window, "Club") == 1


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_a_number_key_does_not_change_the_screen_behind_the_preview(
    qapp: QApplication, window: NativeWindow, screen: str, opened_by
) -> None:
    _preview_open(qapp, window, opened_by(qapp, window, screen))
    before = bridge(window).property("screen")
    _press(window, Qt.Key.Key_3)
    pump(qapp, 10)
    assert bridge(window).property("screen") == before == screen, "3 did not change the screen behind it"
    assert bridge(window).sheets.kind == "preview"


@pytest.mark.parametrize("opened_by", [_duplicate, _paste], ids=["duplicate", "ctrl-v"])
def test_the_keyboard_goes_back_to_the_material_window_when_the_preview_closes(
    qapp: QApplication, window: NativeWindow, opened_by
) -> None:
    _preview_open(qapp, window, opened_by(qapp, window, "week"))
    _press(window, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: bridge(window).sheets.kind == "", what="Esc to close the preview")
    quick = quick_of(window)
    wait_until(qapp, lambda: QApplication.focusWidget() is quick, what="the keyboard to come back")
    pump(qapp, 20)
    # Material's own keys work again.
    QTest.keyClick(quick, Qt.Key.Key_3)
    pump(qapp, 10)
    assert bridge(window).property("screen") == "month"
