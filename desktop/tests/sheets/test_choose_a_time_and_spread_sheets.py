"""Choose a time and Spread: what each offers, what the window reads back after them, how Esc answers,
and the line that says a chosen time clashes with a fixed one. Where their labels sit and how the
clash line is coloured are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QStandardPaths, Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QPushButton

from desktop.native.fields import DayPicker, Stepper
from desktop.native.widgets import ChooseTimeDialog, SpreadDialog
from desktop.tests.sheets.support_dialogs import ESSAY, WEEK, choose_time, shown, soccer, styled
from desktop.tests.window_support import free

WAITING_45 = {"id": "w", "title": "Essay", "duration_min": 45, "days": [1, 2]}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-choose-a-time-test"])


def test_choose_a_time_has_day_pills_a_length_stepper_and_choose_this_time(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    dialog = shown(qapp, ChooseTimeDialog(parent, WAITING_45, WEEK, [1, 2], [], None, 1))
    assert not isinstance(dialog.day, QComboBox)
    assert isinstance(dialog.day, DayPicker)
    assert [button.text() for button in dialog.day.buttons] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]
    assert dialog.day.days() == [1]
    assert not dialog.day.buttons[0].isEnabled()
    dialog.day.buttons[2].click()
    assert dialog.day.days() == [2]
    assert isinstance(dialog.length.parentWidget(), Stepper)
    assert dialog.length.value() == 45
    dialog.length.parentWidget().more.click()
    assert dialog.length.value() == 60
    ok = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
    assert ok.text() == "Choose this time"
    free(dialog)
    free(parent)


def test_choose_a_time_and_spread_give_back_what_was_picked_and_esc_cancels(qapp: QApplication) -> None:
    """What the window reads after Choose a time and Spread is the day and minute, and the session
    length and first day, as before they were sheets. Esc is Cancel."""
    parent, _palette = styled(qapp)
    chosen = shown(qapp, choose_time(parent))
    assert chosen.choice() == (1, 16 * 60), "opens on today, Tuesday, at 16:00"
    chosen.day.set_days([2])
    chosen.start.setTime(QTime(17, 30))
    assert chosen.choice() == (2, 17 * 60 + 30)
    ok = chosen.buttons.button(chosen.buttons.StandardButton.Ok)
    ok.click()
    assert chosen.result() == QDialog.DialogCode.Accepted
    assert chosen.choice() == (2, 17 * 60 + 30)
    free(chosen)
    again = shown(qapp, choose_time(parent))
    QTest.keyClick(again, Qt.Key.Key_Escape)
    assert again.result() == QDialog.DialogCode.Rejected and not again.isVisible()
    free(again)
    spread = shown(qapp, SpreadDialog(parent, {**ESSAY, "unplanned_min": 120}, WEEK))
    assert spread.session_min() == 60 and spread.from_iso() == WEEK
    spread.session.setCurrentIndex(spread.session.findData(90))
    spread.from_date.setDate(QDate(2026, 9, 21))
    assert (spread.session_min(), spread.from_iso()) == (90, "2026-09-21")
    next(item for item in spread.findChildren(QPushButton) if item.text() == "Preview sessions").click()
    assert spread.result() == QDialog.DialogCode.Accepted
    free(spread)
    escaped = shown(qapp, SpreadDialog(parent, ESSAY, WEEK))
    QTest.keyClick(escaped, Qt.Key.Key_Escape)
    assert escaped.result() == QDialog.DialogCode.Rejected and not escaped.isVisible()
    free(escaped)
    free(parent)


def test_choose_a_times_conflict_line_names_the_clash_and_goes_when_there_is_none(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    waiting = {"id": "w", "title": "Essay", "duration_min": 60, "days": [1, 2]}
    sheet = shown(qapp, ChooseTimeDialog(parent, waiting, WEEK, [1, 2], [soccer()], None, 1))
    row = sheet.beside_row
    assert row.objectName() == "conflictRow" and row.isVisible()
    assert sheet.beside.text() == "Soccer practice is at that time too. Both will show, side by side."
    mark = row.findChild(QLabel, "conflictMark")
    assert mark is not None and not mark.pixmap().isNull(), "a warning mark, drawn as the app's icons are"
    sheet.day.set_days([2])
    for _ in range(6):
        qapp.processEvents()
    assert not row.isVisible(), "no clash, no row"
    free(sheet)
    free(parent)
