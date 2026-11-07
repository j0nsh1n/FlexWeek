"""One Plan is one Undo: the notice says what the plan did and its Undo takes every block back, Replan all
is one step, a plan made as homework is added belongs to the add's step, a later save drops the notice, a
plan that places nothing offers no Undo, and a plan waits for a failed save."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from desktop.native.calendar import date_for_day, sunday_due
from desktop.native.widgets import HomeworkDialog, Toast
from desktop.native.window import NativeWindow
from desktop.tests.sheets.support_plan import (
    opened_with,
    press_solve,
    session_of,
    settled,
    stored_blocks,
    window,  # noqa: F401
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_plan_says_what_it_did_with_an_undo_that_takes_it_all_back(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    for key, title in (("poster", "Science poster"), ("vocab", "Spanish vocab")):
        session.add_homework(
            {
                "id": key,
                "title": title,
                "due": sunday_due(session.week_start),
                "estimate_min": 45,
                "revision": 0,
            }
        )
    session.save()
    settled(qapp, window)
    before = stored_blocks(window)
    shown: list[tuple[str, str]] = []
    show = Toast.show_message

    def recorded(toast: Toast, text: str, button: str = "", callback=None) -> None:
        shown.append((text, button))
        show(toast, text, button, callback)

    monkeypatch.setattr(Toast, "show_message", recorded)
    press_solve(window)
    settled(qapp, window)
    monkeypatch.undo()
    assert shown == [("Placed 3 homework blocks.", "Undo")], "said once, with its Undo, not rewrapped"
    planned = stored_blocks(window)
    assert planned != before
    assert window.toast.button.isVisible()
    assert window.toast.text() == "Placed 3 homework blocks."
    assert window.toast.button.accessibleName() == "Undo" and window.toast.button.text().startswith("Undo")

    window.toast.button.click()
    settled(qapp, window)
    assert stored_blocks(window) == before, "one Undo takes back every block the plan placed"
    assert not window.toast.button.isVisible()
    assert session.can_redo()

    session.redo()
    settled(qapp, window)
    assert stored_blocks(window) == planned


def test_replan_all_is_one_undo_step(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    press_solve(window)
    settled(qapp, window)
    session.add_homework(
        {
            "id": "poster",
            "title": "Science poster",
            "due": sunday_due(session.week_start),
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    before = stored_blocks(window)
    window.findChild(QPushButton, "replanAll").click()
    settled(qapp, window)
    assert stored_blocks(window) != before
    assert window.toast.button.accessibleName() == "Undo" and window.toast.button.text().startswith("Undo")
    window.toast.button.click()
    settled(qapp, window)
    assert stored_blocks(window) == before


def test_automatic_plan_stays_in_the_add_homework_undo_step(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    session.preferences = {**(session.preferences or {}), "planning_style": "auto"}

    def add(dialog: HomeworkDialog) -> int:
        dialog.title.setText("Spanish vocab")
        dialog.due.date.setDate(QDate.fromString(sunday_due(session.week_start)[:10], "yyyy-MM-dd"))
        dialog.estimate.setValue(45)
        dialog.accept()
        return QDialog.DialogCode.Accepted

    opened_with(monkeypatch, add)
    window._add_homework()
    settled(qapp, window)
    added = next(item for item in session.assignments.values() if item["title"] == "Spanish vocab")
    assignment_id = added["id"]
    assert session_of(window, assignment_id).get("start")
    assert not window.toast.button.isVisible(), "the added homework owns this Undo step"

    session.undo()
    settled(qapp, window)
    assert assignment_id not in session.assignments
    assert not any(block.get("assignment_id") == assignment_id for block in session.blocks)
    session.redo()
    settled(qapp, window)
    assert assignment_id in session.assignments
    assert session_of(window, assignment_id).get("start")


def test_plan_undo_notice_disappears_after_a_later_save(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    press_solve(window)
    settled(qapp, window)
    assert window.toast.button.isVisible()

    session.add_homework(
        {
            "id": "next",
            "title": "New assignment",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    assert not window.toast.button.isVisible(), "the old Plan Undo must not undo the new assignment"
    session.undo()
    settled(qapp, window)
    assert "next" not in session.assignments
    assert session_of(window, "math").get("start"), "the earlier plan remains"


def test_a_plan_that_places_nothing_does_not_offer_a_false_undo(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.complete_homework("math")
    session.add_homework(
        {
            "id": "overdue",
            "title": "Overdue worksheet",
            "due": date_for_day(session.week_start, 2),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    before = stored_blocks(window)
    undo_steps = len(session._undo)
    session.solve()
    settled(qapp, window)
    assert stored_blocks(window) == before
    assert len(session._undo) == undo_steps, "no plan change means no Undo step"
    assert not window.toast.button.isVisible(), "no Undo for a plan that could place nothing"


def test_plan_waits_for_a_failed_save_before_offering_undo(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    before = stored_blocks(window)
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "failed-save"}
    # The autosave tick would retry the failed save and finish it mid-test.
    window._autosave.stop()
    press_solve(window)
    qapp.processEvents()
    assert stored_blocks(window) == before
    assert session.message == "Saving your last change… Plan will work in a moment."
    assert not window.toast.button.isVisible()
