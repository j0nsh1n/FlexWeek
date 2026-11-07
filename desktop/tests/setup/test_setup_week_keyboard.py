"""Setup's week page by keyboard: its fields have names, Tab from the school days reaches every activity row
before Next, removing an activity keeps the keyboard in the list, and retyping Start leaves End alone."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.setup import SetupPage
from desktop.tests.setup.support_wizard import WEEK, state
from desktop.tests.sheets.support_keys import fields_of, hhmm, press, tab_in, type_text, unnamed, up
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.fixture()
def setup(qapp):
    """Setup on its week page: motion off so nothing slides, the first activity row empty."""
    page = SetupPage()
    page.motion = "off"
    page.resize(1100, 720)
    page.open(state())
    page._show(WEEK)
    up(qapp, page)
    yield page
    page.hide()
    free(page)


def test_every_field_has_a_name_that_is_not_its_value_and_combos_have_a_buddy(setup) -> None:
    assert fields_of(setup), "found no fields"
    assert unnamed(setup) == []


@pytest.mark.parametrize("which", ["school", "activity"])
def test_retyping_start_leaves_end_alone(setup, which) -> None:
    if which == "school":
        times = setup.school_times
    else:
        row = setup.activities[0]
        row.name.setText("Soccer")
        row.days.set_days([1])
        times = row.times
    times.end.setTime(QTime(18, 0))
    before = hhmm(times.end)
    tab_in(times.start)
    type_text(times.start, "09:15")
    press(times.start, Qt.Key.Key_Tab)
    assert (hhmm(times.start), hhmm(times.end)) == ("09:15", before)


def tab_walk(page, start: QWidget, limit: int = 120) -> list[QWidget]:
    start.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    seen = [QApplication.focusWidget()]
    for _ in range(limit):
        press(page, Qt.Key.Key_Tab)
        now = QApplication.focusWidget()
        if now is page.next or now in seen:
            seen.append(now)
            break
        seen.append(now)
    return seen


@pytest.mark.parametrize("rows", [1, 2], ids=["one-activity", "two-activities"])
def test_tab_from_school_reaches_every_activity_before_next(qapp, setup, rows) -> None:
    while len(setup.activities) < rows:
        setup._add_activity("Band", [2])
    qapp.processEvents()
    first_day = next(b for b in setup.school_days.findChildren(QPushButton) if b.isVisible())
    walked = tab_walk(setup, first_day)
    assert walked[-1] is setup.next, "Tab never reached Next"
    missing = [row.name.text() or "(empty)" for row in setup.activities if row.name not in walked]
    assert missing == [], f"reached Next before activity rows {missing}"


def remove_by_keyboard(page, row) -> None:
    remove = next(b for b in row.findChildren(QPushButton) if b.accessibleName() == "Remove this activity")
    remove.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    press(remove, Qt.Key.Key_Space)
    for _ in range(3):
        QApplication.processEvents()


def test_removing_activities_keeps_the_keyboard_in_the_list(qapp, setup) -> None:
    while len(setup.activities) < 3:
        setup._add_activity(f"Club {len(setup.activities)}", [2])
    qapp.processEvents()
    first, middle, last = setup.activities[:3]
    remove_by_keyboard(setup, middle)
    assert QApplication.focusWidget() is last.name, "after removing the middle row"
    remove_by_keyboard(setup, last)
    assert QApplication.focusWidget() is first.name, "after removing the last row"
    remove_by_keyboard(setup, first)
    assert QApplication.focusWidget() is setup.add_activity, "after removing the only row"
