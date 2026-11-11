"""Go to a date from the Material Week and Month titles: the title opens a small month; picking a day
jumps to that day's week (Week) or month (Month). The title takes the keyboard with Tab; Enter or Space
opens it, the arrows move in the month, Enter picks, Esc closes and gives the focus back to the title.

Expected values come from the calendar: the account opens on the week of Monday 2 November 2026 (the shared
fake clock), so a pick of Friday 20 November lands on the week of Monday 16 November, and a pick in December
lands on 2026-12.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump, qml, visuals  # noqa: E402
from desktop.tests.sheets.support_material_sheets import bridge, click, material_week  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

FIRST_WEEK = "2026-11-02"


def quick_of(window: NativeWindow):
    return window._material_page._quick


def picker_of(root: QObject) -> QObject:
    return qml(root, "datePicker")


def is_open(root: QObject) -> bool:
    return picker_of(root).property("open") is True


def day_cell(root: QObject, text: str) -> QObject:
    """The cell of the picker's month whose number is `text` (a number only the shown month has)."""
    mini = qml(root, "datePickerMonth")
    found = [
        item
        for item in visuals(mini)
        if str(item.objectName()).startswith("cell") and str(item.property("text")) == text
    ]
    assert len(found) == 1, (text, len(found))
    return found[0]


def on_week(qapp, window: NativeWindow) -> QObject:
    root = material_week(qapp, window)
    assert window.session.week_start == FIRST_WEEK
    return root


def on_month(qapp, window: NativeWindow) -> QObject:
    root = material_week(qapp, window)
    bridge(window).showPage("month")
    wait_until(qapp, lambda: root.findChild(QObject, "materialMonth") is not None)
    wait_until(qapp, lambda: window.session.selected_month == "2026-11")
    pump(qapp, 20)
    return root


def title_of(root: QObject) -> QObject:
    return qml(root, "materialTitle")


def key(window: NativeWindow, which: Qt.Key) -> None:
    QTest.keyClick(quick_of(window), which)
    pump(QApplication.instance(), 10)


def title_picked_by(window: NativeWindow, root: QObject, how: str) -> None:
    title = title_of(root)
    if how == "click":
        click(window, title)
    else:
        title.forceActiveFocus()
        pump(QApplication.instance(), 5)
        key(window, Qt.Key.Key_Return if how == "enter" else Qt.Key.Key_Space)
    wait_until(None, lambda: is_open(root), what="the date picker to open")


@pytest.mark.parametrize("how", ["click", "enter", "space"])
def test_the_week_title_opens_the_month_picker(qapp, window: NativeWindow, how: str) -> None:
    root = on_week(qapp, window)
    assert not is_open(root)
    title_picked_by(window, root, how)
    assert qml(root, "datePickerMonth").property("month") == 11


def test_picking_a_day_with_the_mouse_jumps_to_that_days_week(qapp, window: NativeWindow) -> None:
    root = on_week(qapp, window)
    title_picked_by(window, root, "click")
    click(window, day_cell(root, "20"))
    wait_until(qapp, lambda: window.session.week_start == "2026-11-16", what="the week of 16 November")
    assert not is_open(root)


def test_picking_a_day_with_the_keyboard_jumps_and_gives_the_focus_back_to_the_title(
    qapp, window: NativeWindow
) -> None:
    root = on_week(qapp, window)
    title_picked_by(window, root, "enter")
    # The month opens on the week on view: Monday the 2nd is the cursor; Down is a week on.
    key(window, Qt.Key.Key_Down)
    key(window, Qt.Key.Key_Return)
    wait_until(qapp, lambda: window.session.week_start == "2026-11-09", what="the week of 9 November")
    assert not is_open(root)
    assert title_of(root).property("activeFocus") is True


def test_escape_closes_the_picker_keeps_the_week_and_gives_the_focus_back(qapp, window: NativeWindow) -> None:
    root = on_week(qapp, window)
    title_picked_by(window, root, "enter")
    key(window, Qt.Key.Key_Escape)
    assert not is_open(root)
    assert title_of(root).property("activeFocus") is True
    assert window.session.week_start == FIRST_WEEK


def test_the_month_buttons_and_page_keys_change_the_picker_month(qapp, window: NativeWindow) -> None:
    root = on_week(qapp, window)
    title_picked_by(window, root, "click")
    mini = qml(root, "datePickerMonth")
    click(window, qml(root, "datePickerNext"))
    assert (mini.property("year"), mini.property("month")) == (2026, 12)
    key(window, Qt.Key.Key_PageUp)
    key(window, Qt.Key.Key_PageUp)
    assert (mini.property("year"), mini.property("month")) == (2026, 10)
    click(window, qml(root, "datePickerPrevious"))
    assert (mini.property("year"), mini.property("month")) == (2026, 9)


def test_tab_reaches_the_title_in_week_and_month(qapp, window: NativeWindow) -> None:
    root = on_week(qapp, window)
    for screen in ("week", "month"):
        bridge(window).showPage(screen)
        pump(qapp, 30)
        title = title_of(root)
        qml(root, "navDay").forceActiveFocus()
        pump(qapp, 5)
        reached = False
        for _ in range(12):
            key(window, Qt.Key.Key_Tab)
            if title.property("activeFocus") is True:
                reached = True
                break
        assert reached, f"Tab never reached the title on {screen}"


def test_the_day_title_does_not_open_a_picker(qapp, window: NativeWindow) -> None:
    root = on_week(qapp, window)
    bridge(window).showPage("day")
    pump(qapp, 30)
    click(window, title_of(root))
    pump(qapp, 10)
    assert not is_open(root)


def test_the_month_title_opens_the_picker_and_a_pick_jumps_to_that_month(qapp, window: NativeWindow) -> None:
    root = on_month(qapp, window)
    title_picked_by(window, root, "click")
    click(window, qml(root, "datePickerNext"))
    # Opens on the 1st of December; Enter picks it.
    key(window, Qt.Key.Key_Return)
    wait_until(qapp, lambda: window.session.selected_month == "2026-12", what="December on the Month screen")
    assert not is_open(root)


def test_a_mouse_pick_in_the_month_picker_jumps_to_that_month(qapp, window: NativeWindow) -> None:
    root = on_month(qapp, window)
    title_picked_by(window, root, "enter")
    click(window, qml(root, "datePickerPrevious"))
    click(window, day_cell(root, "15"))
    wait_until(qapp, lambda: window.session.selected_month == "2026-10", what="October on the Month screen")


def test_escape_in_the_month_picker_returns_the_focus_to_the_title(qapp, window: NativeWindow) -> None:
    root = on_month(qapp, window)
    title_picked_by(window, root, "space")
    key(window, Qt.Key.Key_Escape)
    assert not is_open(root)
    assert title_of(root).property("activeFocus") is True
    assert window.session.selected_month == "2026-11"


def test_the_picker_closes_when_the_rail_changes_the_screen(qapp, window: NativeWindow) -> None:
    """Left open over Day, a pick would quietly change another screen's date and keep keys switched off."""
    root = on_week(qapp, window)
    click(window, title_of(root))
    pump(qapp, 10)
    assert is_open(root)
    click(window, qml(root, "navDay"))
    pump(qapp, 20)

    assert bridge(window).screen == "day"
    assert not is_open(root)
