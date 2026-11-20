# ruff: noqa: F811
"""The due time on the Material homework sheet, and spreading over days.

What a student sees: a time they set shows again when they open the homework; no time means the end of the
day; an old end-of-day deadline stays exactly as stored until they change the deadline; homework due today
with no time is accepted; old overdue homework can still be edited, while a deadline they change is checked.
Spreading is offered only for a long homework that is not pinned and has no sessions yet.

The week the fixtures build: the clock is Thursday 19:00.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
    type_homework,
)

DUE_PASSED = "That due time has passed. Choose a later one."


def _day(shell: NativeWindow, offset: int) -> str:
    """The date `offset` days after the week's first day (Monday), as an ISO date."""
    return (datetime.fromisoformat(shell.session.week_start) + timedelta(days=offset)).date().isoformat()


def _add(qapp: QApplication, shell: NativeWindow, due: str, *, estimate: int = 60) -> str:
    shell.session.add_homework(
        {"id": "hw", "title": "Lab report", "due": due, "estimate_min": estimate, "revision": 0}
    )
    shell.session.save()
    settle(qapp, shell)
    return "hw"


def test_a_stored_due_time_shows_when_the_homework_is_opened_and_saving_keeps_it(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    due = f"{_day(shell, 4)}T17:30"
    sheets.editHomework(_add(qapp, shell, due))
    assert sheets.form["dueDate"] == _day(shell, 4)
    assert sheets.form["dueTime"] == "17:30"
    sheets.setText("title", "Lab report, final")
    sheets.save()
    assert shell.session.assignments["hw"]["due"] == due
    settle(qapp, shell)


def test_no_time_means_the_end_of_the_day(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.editHomework(_add(qapp, shell, f"{_day(shell, 4)}T17:30"))
    sheets.setText("dueTime", "")
    sheets.save()
    assert shell.session.assignments["hw"]["due"] == f"{_day(shell, 4)}T23:59"
    settle(qapp, shell)


@pytest.mark.parametrize("old", ["{day}", "{day}T23:59"], ids=["date only", "23:59"])
def test_an_old_end_of_day_deadline_stays_as_stored_until_the_deadline_is_changed(
    qapp: QApplication, shell: NativeWindow, sheets, old: str
) -> None:
    stored = old.format(day=_day(shell, 4))
    sheets.editHomework(_add(qapp, shell, stored))
    assert sheets.form["dueTime"] == "", "an old end of day shows as End of day"
    sheets.setText("title", "Lab report, final")
    sheets.save()
    assert shell.session.assignments["hw"]["due"] == stored
    settle(qapp, shell)

    sheets.editHomework("hw")
    sheets.setText("dueDate", _day(shell, 5))
    sheets.save()
    assert shell.session.assignments["hw"]["due"] == f"{_day(shell, 5)}T23:59"
    settle(qapp, shell)


def test_homework_due_today_with_no_time_is_accepted(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    """Thursday 19:00 is now, and the end of Thursday has not come."""
    sheets.openHomework()
    type_homework(sheets, "Quick quiz")
    sheets.next()
    sheets.setText("dueDate", _day(shell, 3))
    sheets.next()
    assert sheets.form["dueProblem"] == ""
    assert sheets.form["step"] == 2
    sheets.save()
    assert sheets.kind == ""
    made = next(item for item in shell.session.assignments.values() if item["title"] == "Quick quiz")
    assert made["due"] == f"{_day(shell, 3)}T23:59"
    settle(qapp, shell)


def test_old_overdue_homework_can_be_saved_while_its_deadline_is_untouched(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.editHomework(_add(qapp, shell, f"{_day(shell, 0)}T10:00"))
    assert sheets.form["dueProblem"] == ""
    sheets.setText("title", "Lab report, late")
    sheets.save()
    assert sheets.kind == "", "the sheet closed: it was saved"
    assert shell.session.assignments["hw"]["title"] == "Lab report, late"
    assert shell.session.assignments["hw"]["due"] == f"{_day(shell, 0)}T10:00"
    settle(qapp, shell)


def test_a_changed_deadline_that_has_passed_is_refused(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.editHomework(_add(qapp, shell, f"{_day(shell, 0)}T10:00"))
    sheets.setText("dueDate", _day(shell, 1))
    sheets.save()
    assert sheets.kind == "homework", "the sheet stays open"
    assert sheets.form["dueProblem"] == DUE_PASSED
    assert shell.session.assignments["hw"]["due"] == f"{_day(shell, 0)}T10:00"


# Spread over days ---------------------------------------------------------------------------------------


def _new_homework_at_length(sheets, shell: NativeWindow, minutes: str) -> None:
    sheets.openHomework()
    type_homework(sheets, "Project")
    sheets.next()
    sheets.setText("dueDate", _day(shell, 6))
    sheets.next()
    sheets.setText("estimate", minutes)


@pytest.mark.parametrize(("minutes", "offered"), [("45", False), ("60", True), ("120", True)])
def test_spreading_is_offered_only_from_sixty_minutes(
    shell: NativeWindow, sheets, minutes: str, offered: bool
) -> None:
    _new_homework_at_length(sheets, shell, minutes)
    assert sheets.form["spreadShown"] is offered


def test_spreading_is_not_offered_with_a_pinned_time(shell: NativeWindow, sheets) -> None:
    _new_homework_at_length(sheets, shell, "120")
    assert sheets.form["spreadShown"] is True
    sheets.setText("when", "fixed")
    assert sheets.form["spreadShown"] is False
    sheets.setText("when", "plan")
    assert sheets.form["spreadShown"] is True


def test_spreading_is_not_offered_when_the_homework_already_has_sessions(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    """A homework already spread over two sessions is not offered the choice again, whatever its length."""
    shell.session.add_block(
        {
            "id": "essay-2",
            "title": "History essay",
            "kind": "flexible",
            "category": "assignments",
            "start": "17:00",
            "days": [4],
            "duration_min": 60,
            "assignment_id": "essay",
        }
    )
    shell.session.save()
    settle(qapp, shell)
    sheets.editHomework("essay")
    sheets.setText("estimate", "120")
    assert sheets.form["spreadShown"] is False
