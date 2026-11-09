# ruff: noqa: F811
"""The availability dialog: study hours, protected time and the cut-off, as a student adds, removes and
reads them. (How its week strip is painted is a picture: sheets.availability_strip.)"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from desktop.native.widgets import AvailabilityDialog  # noqa: E402
from desktop.tests.day.support_layouts_window import qapp  # noqa: E402, F401

SETUP_HOURS = [
    {"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00"},
    {"days": [5, 6], "start": "10:00", "end": "12:00"},
]
PIANO = {"days": [1, 3], "start": "17:00", "duration_min": 90, "kind": "downtime"}


def availability(preferences: dict, palette: dict | None = None) -> AvailabilityDialog:
    return AvailabilityDialog(None, preferences, ["Math", "Reading"], palette)


def plus(dialog, kind: str, day: int) -> QPushButton:
    buttons = dialog.findChildren(QPushButton, f"{kind}Add")
    return next(button for button in buttons if button.property("day") == day)


def day_row(dialog, kind: str, day: int) -> list[str]:
    """The words on one day's row of a tab: its chips, then its +."""
    row = plus(dialog, kind, day).parentWidget()
    return [button.text() for button in row.findChildren(QPushButton)]


def test_each_day_shows_its_hours_as_chips_and_one_plus(qapp: QApplication) -> None:
    math = {"days": [2], "start": "07:00", "end": "08:00", "subject": "Math"}
    dialog = availability({"work_windows": [*SETUP_HOURS, math], "protected": [PIANO]})
    assert day_row(dialog, "study", 0) == ["16:00–21:00  ×", "+"]
    assert day_row(dialog, "study", 2) == ["16:00–21:00  ×", "07:00–08:00 Math  ×", "+"]
    assert day_row(dialog, "study", 6) == ["10:00–12:00  ×", "+"]
    assert day_row(dialog, "protected", 1) == ["17:00–18:30 Downtime  ×", "+"]
    assert day_row(dialog, "protected", 0) == ["+"], "an empty day shows only its +"
    for button in dialog.findChildren(QPushButton):
        if button.text() == "+":
            assert button.property("outlined") is True, "add buttons are outlined"
        if button.text().endswith("×"):
            assert button.property("tonal") is True, "chips are tinted"
    assert dialog.study_empty.isHidden() and dialog.protected_empty.isHidden()
    dialog.deleteLater()


def test_an_empty_tab_says_so_in_grey(qapp: QApplication) -> None:
    dialog = availability({})
    assert dialog.protected_empty.text() == "Nothing protected yet. Add practice, family time or a job."
    assert dialog.protected_empty.objectName() == "cardNote"
    assert not dialog.study_empty.isHidden() and not dialog.protected_empty.isHidden()
    assert day_row(dialog, "study", 3) == ["+"]
    dialog.deleteLater()


def test_the_tabs_show_study_hours_protected_time_and_the_cutoff(qapp: QApplication) -> None:
    dialog = availability({"work_windows": SETUP_HOURS, "day_cutoff": "21:30"})
    assert [button.text() for button in dialog.tabs.buttons()] == ["Study hours", "Protected", "Cut-off"]
    assert dialog.pages.currentIndex() == 0
    for index, shown in ((1, "protectedAdd"), (2, "availabilityCutoff"), (0, "studyAdd")):
        dialog.tabs.buttons()[index].click()
        page = dialog.pages.currentWidget()
        assert page.findChild(QWidget, shown) is not None, shown
    dialog.tabs.buttons()[2].click()
    assert dialog.day_cutoff() == "21:30"
    dialog.cutoff.setCurrentIndex(dialog.cutoff.findData(None))
    assert dialog.day_cutoff() is None
    assert "The line" not in dialog.legend.text(), "no cut-off, no line to explain"
    dialog.deleteLater()


def test_removing_a_chip_takes_only_that_day_out_of_a_shared_window(qapp: QApplication) -> None:
    """Setup saves Monday to Friday as one window. Tuesday's × leaves the other four days with it."""
    dialog = availability({"work_windows": SETUP_HOURS})
    tuesday = next(
        chip for chip in dialog.findChildren(QPushButton, "studyChip") if "Tuesday" in chip.accessibleName()
    )
    tuesday.click()
    assert dialog.work_windows() == [
        {"days": [0, 2, 3, 4], "start": "16:00", "end": "21:00"},
        {"days": [5, 6], "start": "10:00", "end": "12:00"},
    ]
    assert day_row(dialog, "study", 1) == ["+"]
    dialog.deleteLater()


def test_adding_hours_on_a_day_saves_them_with_any_equal_hours(qapp: QApplication) -> None:
    dialog = availability({"work_windows": SETUP_HOURS})
    plus(dialog, "study", 5).click()
    assert dialog.picker.isVisibleTo(dialog)
    dialog.picker_start.setTime(QTime(16, 0))
    dialog.picker_end.setTime(QTime(21, 0))
    dialog.picker_add.click()
    assert not dialog.picker.isVisibleTo(dialog)
    assert dialog.work_windows() == [
        {"days": [0, 1, 2, 3, 4, 5], "start": "16:00", "end": "21:00"},
        {"days": [5, 6], "start": "10:00", "end": "12:00"},
    ]
    assert day_row(dialog, "study", 5) == ["10:00–12:00  ×", "16:00–21:00  ×", "+"]
    dialog.deleteLater()


def test_study_hours_can_be_kept_for_one_subject(qapp: QApplication) -> None:
    dialog = availability({})
    dialog._open_picker(kind="study", day=0)
    dialog.picker_start.setTime(QTime(15, 30))
    dialog.picker_end.setTime(QTime(17, 0))
    dialog.picker_subject.setCurrentIndex(dialog.picker_subject.findData("Math"))
    dialog.picker_add.click()
    assert dialog.work_windows() == [{"days": [0], "start": "15:30", "end": "17:00", "subject": "Math"}]
    assert day_row(dialog, "study", 0) == ["15:30–17:00 Math  ×", "+"]
    dialog._open_picker(kind="study", day=0)
    dialog.picker_end.setTime(QTime(15, 0))
    dialog.picker_add.click()
    assert dialog.error.text() == "End needs to be later than Start (16:00)."
    assert len(dialog.work_windows()) == 1
    dialog.deleteLater()


def test_protected_time_is_added_with_its_kind_and_never_overlaps(qapp: QApplication) -> None:
    dialog = availability({"protected": [PIANO]})
    dialog._open_picker(kind="protected", day=3)
    assert not dialog.picker_subject.isVisibleTo(dialog) and dialog.picker_kind.isVisibleTo(dialog)
    dialog.picker_start.setTime(QTime(18, 0))
    dialog.picker_end.setTime(QTime(19, 0))
    dialog.picker_add.click()
    assert dialog.error.text() == "That overlaps protected time already on Thursday."
    dialog.picker_start.setTime(QTime(18, 30))
    dialog.picker_kind.setCurrentIndex(dialog.picker_kind.findData("meal"))
    dialog.picker_add.click()
    assert dialog.error.text() == ""
    assert dialog.protected() == [PIANO, {"days": [3], "kind": "meal", "start": "18:30", "duration_min": 30}]
    dialog.deleteLater()


def test_protected_time_shows_and_saves_its_own_name(qapp: QApplication) -> None:
    dialog = availability({"protected": [{**PIANO, "title": "Piano"}]})
    assert day_row(dialog, "protected", 1) == ["17:00–18:30 Piano  ×", "+"]
    dialog._open_picker(kind="protected", day=2)
    assert dialog.picker_title.isVisibleTo(dialog) and not dialog.picker_subject.isVisibleTo(dialog)
    assert dialog.picker_title.placeholderText() == "e.g. Piano"
    dialog.picker_start.setTime(QTime(17, 0))
    dialog.picker_end.setTime(QTime(18, 30))
    dialog.picker_title.setText("  Piano ")
    dialog.picker_add.click()
    dialog._open_picker(kind="protected", day=5)
    assert dialog.picker_title.text() == "", "each new time starts without a name"
    dialog.picker_start.setTime(QTime(9, 0))
    dialog.picker_end.setTime(QTime(10, 0))
    dialog.picker_add.click()
    assert dialog.protected() == [
        {"days": [1, 2, 3], "start": "17:00", "duration_min": 90, "kind": "downtime", "title": "Piano"},
        {"days": [5], "kind": "downtime", "start": "09:00", "duration_min": 60},
    ]
    assert day_row(dialog, "protected", 5) == ["09:00–10:00 Downtime  ×", "+"]
    dialog.deleteLater()
