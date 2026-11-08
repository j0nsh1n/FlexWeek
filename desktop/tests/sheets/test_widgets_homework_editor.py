"""The Widgets Add homework and Edit homework sheet: the due day and the time it only shows when asked,
an old end-of-day due kept as stored, the length hint, and the details that sit behind More details.
How wide the sheet is and where it scrolls are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QStandardPaths, QTime
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.widgets import SLOT_HINT, HomeworkDialog
from desktop.tests.test_homework_form import go_when


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-homework-editor-test"])


def _homework(due: str) -> dict:
    return {
        "id": "oral",
        "title": "French oral",
        "due": due,
        "estimate_min": 30,
        "revision": 0,
        "notes": "",
        "links": [],
        "checklist": [],
    }


def test_an_off_grid_estimate_says_to_use_a_multiple_of_fifteen(qapp: QApplication) -> None:
    dialog = HomeworkDialog(None, None, "2026-09-14")
    dialog.title.setText("Essay")
    dialog.estimate.setValue(20)
    dialog.show()
    qapp.processEvents()
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    hint = dialog.findChild(QLabel, "homeworkEstimateHint")
    assert hint.text() == SLOT_HINT
    assert hint.isVisible() and hint.property("problem") is True
    assert not dialog.error.isVisible(), "said once, beside the box"
    dialog.close()


def test_homework_optional_fields_sit_behind_more_details(qapp: QApplication) -> None:
    blank = HomeworkDialog(None, None, "2026-09-14")
    blank.show()
    qapp.processEvents()
    assert blank.findChild(type(blank.more_details), "homeworkMoreDetails") is not None
    assert blank._details.isVisible() is False
    blank.more_details.setChecked(True)
    assert blank._details.isVisible() is True
    blank.close()

    filled = HomeworkDialog(
        None,
        {
            "id": "math",
            "title": "Math worksheet",
            "due": "2026-09-14T21:00",
            "estimate_min": 45,
            "revision": 0,
            "course": "Math",
            "notes": "",
            "links": [],
            "checklist": [],
        },
        "2026-09-14",
    )
    filled.show()
    qapp.processEvents()
    assert filled.more_details.isChecked() is True
    assert filled._details.isVisible() is True
    filled.close()


def test_new_homework_is_due_on_a_day_and_a_time_only_when_asked(qapp: QApplication) -> None:
    dialog = HomeworkDialog(None, None, "2026-09-14")
    dialog.show()
    qapp.processEvents()
    assert dialog.due.value() == "2026-09-15", "tomorrow, whatever the hour"
    go_when(dialog)
    assert not dialog.due.time.isVisible(), "no time box until the student says it is due at one"
    dialog.due.timed.setChecked(True)
    assert dialog.due.time.isVisible()
    assert dialog.due.value() == "2026-09-15T15:00", "the end of the school day, 15:00 with none saved"
    dialog.close()


def test_an_old_end_of_day_due_is_kept_as_stored_until_the_deadline_changes(qapp: QApplication) -> None:
    kept = HomeworkDialog(None, _homework("2026-09-20T23:59"), "2026-09-14")
    assert not kept.due.timed.isChecked(), "23:59 was the old way of saying no time"
    kept.title.setText("French oral, part 2")
    kept.accept()
    assert kept.assignment()["due"] == "2026-09-20T23:59"

    moved = HomeworkDialog(None, _homework("2026-09-20T23:59"), "2026-09-14")
    moved.due.date.setDate(QDate(2026, 9, 18))
    moved.accept()
    assert moved.assignment()["due"] == "2026-09-18"


def test_a_due_time_is_shown_and_can_be_taken_away(qapp: QApplication) -> None:
    dialog = HomeworkDialog(None, _homework("2026-09-17T10:15"), "2026-09-14")
    assert dialog.due.timed.isChecked() and dialog.due.time.time() == QTime(10, 15)
    dialog.due.time.setTime(QTime(8, 30))
    dialog.accept()
    assert dialog.assignment()["due"] == "2026-09-17T08:30"

    untimed = HomeworkDialog(None, _homework("2026-09-17T10:15"), "2026-09-14")
    untimed.due.timed.setChecked(False)
    untimed.accept()
    assert untimed.assignment()["due"] == "2026-09-17"
