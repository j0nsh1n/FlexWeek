# ruff: noqa: F811
"""My day as the student uses it: the view buttons and keys that reach it and leave it, the day screens it
opens, and its Finished and Running late buttons reaching what the product already does."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel  # noqa: E402

from desktop.native.layouts.one_thing import OneThingView  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    at_motion_level,
    click,
    fades,
    one_thing,
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)


def test_my_day_puts_planning_away_and_back_brings_it_back(qapp: QApplication, window: NativeWindow) -> None:
    one_thing(window)
    assert window.planner.currentWidget() is window.week_table
    click(window, "viewMyDay")
    assert isinstance(window.planner.currentWidget(), OneThingView)
    assert window.solve_button.isVisible() is True
    assert window.findChild(QAbstractButton, "viewMyDay").isChecked() is True
    assert window.findChild(QAbstractButton, "viewWeek").isChecked() is False
    click(window, "oneBack")
    assert window.planner.currentWidget() is window.week_table
    assert window.solve_button.isVisible() is True
    assert window.findChild(QAbstractButton, "viewWeek").isChecked() is True


def test_the_day_screen_reads_the_real_week_at_the_real_minute(
    qapp: QApplication, window: NativeWindow
) -> None:
    one_thing(window)
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    said = tuple(view.findChild(QLabel, name).text() for name in ("oneLabel", "oneTitle", "oneLine"))
    assert said == ("Now", "History essay", "6:45–7:45 PM")


def test_homework_finished_finishes_it_the_way_the_product_does(
    qapp: QApplication, window: NativeWindow
) -> None:
    one_thing(window)
    click(window, "viewMyDay")
    click(window, "oneFinished")
    settled(qapp, window)
    assert window.session.assignments["essay"]["completed"] is True
    assert window.session.can_undo() is True
    view = window.planner.currentWidget()
    # The ring may set the title over two lines; the words are whole either way.
    title = view.findChild(QLabel, "oneTitle")
    assert (" ".join(title.text().split()), title.accessibleName()) == ("All homework finished",) * 2


def test_finishing_from_my_day_offers_undo_on_the_notice(qapp: QApplication, window: NativeWindow) -> None:
    one_thing(window)
    click(window, "viewMyDay")
    click(window, "oneFinished")
    settled(qapp, window)
    assert window.session.assignments["essay"]["completed"] is True
    assert window.toast.button.isVisible()
    assert window.toast.text() == "Finished History essay."
    assert window.toast.button.accessibleName() == "Undo" and window.toast.button.text().startswith("Undo")


def test_running_late_opens_the_products_own_running_late(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    one_thing(window)
    opened: list[str] = []
    monkeypatch.setattr(NativeWindow, "_open_late", lambda self: opened.append("late"))
    click(window, "viewMyDay")
    click(window, "oneLate")
    assert opened == ["late"]


def test_the_keyboard_reaches_my_day_and_back(qapp: QApplication, window: NativeWindow) -> None:
    """The week grid keeps letter keys for type-ahead, so T has to be taken the way W, D and M are."""
    one_thing(window)
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    day = window.planner.currentWidget()
    assert isinstance(day, OneThingView)
    QTest.keyClick(day, Qt.Key.Key_B)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    QTest.keyClick(window.planner.currentWidget(), Qt.Key.Key_Escape)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    QTest.keyClick(window.planner.currentWidget(), Qt.Key.Key_M)
    wait_until(qapp, lambda: window.planner.currentWidget() is window.month_grid)
    assert window.solve_button.isVisible() is True
    QTest.keyClick(window.month_grid.canvas, Qt.Key.Key_T)
    assert isinstance(window.planner.currentWidget(), OneThingView)


def test_the_view_buttons_leave_a_day_screen(qapp: QApplication, window: NativeWindow) -> None:
    click(window, "viewMyDay")
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_view
    assert window.solve_button.isVisible() is True


def test_signing_out_of_a_day_screen_does_not_leave_the_next_student_in_one(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native import window as window_module

    monkeypatch.setattr(window_module, "confirm", lambda *_args, **_kwargs: True)
    click(window, "viewMyDay")
    click(window, "signOut")
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "authPage")
    assert window._day_mode is False


def test_my_day_opens_whichever_day_screen_was_picked(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "dial", "options": {}}
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    assert type(view).__name__ == "DayDialView"
    # The demo's day dial has no card title: the essay is named in its list row.
    assert "History essay" in [name.text() for name in view.findChildren(QLabel, "dialRowName")]
    click(window, "dialBack")
    assert window.planner.currentWidget() is window.week_table


def test_my_day_changes_its_chrome_and_its_page_in_the_same_frame(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The planning chrome and the rail went at once while the old week still faded, so for a moment
    neither page was on screen as it is. With the rail going, the week stays under the picture of itself
    while My day slides in over it. The two grabs are compared with each other, not with a colour."""
    from PySide6.QtCore import QRect

    at_motion_level(qapp, window, "normal")
    page = window._week_page
    top = window._top_bar.geometry().bottom() + 1
    under_bar = QRect(0, top, page.width(), page.height() - top)
    before = page.grab(under_bar).toImage()
    assert window.rail.isVisible()
    click(window, "viewMyDay")
    assert not window.rail.isVisible() and not window.plan_chrome.isVisible()
    assert page.grab(under_bar).toImage() == before, "the first frame is still the week, rail and all"
    assert window.planner.currentWidget().graphicsEffect() is None, "My day does not fade, it slides over"
    wait_until(qapp, lambda: fades(window) == [], what="the slide ending")
    assert page.grab(under_bar).toImage() != before
