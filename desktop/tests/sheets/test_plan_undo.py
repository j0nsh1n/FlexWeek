# ruff: noqa: F811  (pytest fixtures imported by name)
"""One Plan is one Undo: the notice says what the plan did and its Undo takes every block back, Replan all
is one step, a plan made as homework is added belongs to the add's step, a later save drops the notice, a
plan that places nothing offers no Undo, and a plan waits for a failed save. Run on the Material week."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day, sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, qml
from desktop.tests.sheets.support_plan import (
    session_of,
    settled,
    stored_blocks,
    window,  # noqa: F401
)
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _bridge, _click, _snack
from desktop.tests.week.support_material_page import fresh_material
from desktop.tests.window_support import qapp  # noqa: F401


def _action(window: NativeWindow) -> str:
    return str(_bridge(window).property("snackAction"))


def _press_plan(qapp: QApplication, window: NativeWindow, root) -> None:
    _click(window, qml(root, "planHomework"))
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    settled(qapp, window)


def _undo_on_the_snackbar(qapp: QApplication, window: NativeWindow, root) -> None:
    bar = qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    settled(qapp, window)


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
    root = fresh_material(qapp, window)
    before = stored_blocks(window)
    shown: list[tuple[str, str]] = []
    bridge = _bridge(window)
    note = bridge.note

    def recorded(text: str, *, action: str = "UNDO") -> None:
        shown.append((text, action))
        note(text, action=action)

    monkeypatch.setattr(bridge, "note", recorded)
    _press_plan(qapp, window, root)
    monkeypatch.undo()
    assert shown == [("Placed 3 of 3", "UNDO")], "said once, with its Undo"
    planned = stored_blocks(window)
    assert planned != before
    assert _snack(window) == "Placed 3 of 3" and _action(window) == "UNDO"

    _undo_on_the_snackbar(qapp, window, root)
    assert stored_blocks(window) == before, "one Undo takes back every block the plan placed"
    assert _snack(window) == "Undid planning the week.", "Undo says what it did, with no Undo of its own"
    assert _action(window) == ""
    assert session.can_redo()

    session.redo()
    settled(qapp, window)
    assert stored_blocks(window) == planned


def test_replan_all_is_one_undo_step(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    root = fresh_material(qapp, window)
    _press_plan(qapp, window, root)
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
    _bridge(window).sheets.moreAction("replanAll")
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not session.busy)
    settled(qapp, window)
    assert stored_blocks(window) != before
    assert _action(window) == "UNDO"
    _undo_on_the_snackbar(qapp, window, root)
    assert stored_blocks(window) == before


def test_automatic_plan_stays_in_the_add_homework_undo_step(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.preferences = {**(session.preferences or {}), "planning_style": "auto"}
    fresh_material(qapp, window)
    sheets = _bridge(window).sheets
    sheets.openHomework()
    sheets.setText("title", "Spanish vocab")
    pump(qapp, 20)
    sheets.save()
    wait_until(qapp, lambda: any(item["title"] == "Spanish vocab" for item in session.assignments.values()))
    settled(qapp, window)
    added = next(item for item in session.assignments.values() if item["title"] == "Spanish vocab")
    assignment_id = added["id"]
    assert session_of(window, assignment_id).get("start")
    assert _action(window) == "", "the added homework owns this Undo step; Plan offers no Undo of its own"

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
    root = fresh_material(qapp, window)
    _press_plan(qapp, window, root)
    assert _action(window) == "UNDO"

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
    pump(qapp)
    assert not (_snack(window).startswith("Placed") and _action(window) == "UNDO"), (
        "the old Plan Undo must not undo the new assignment"
    )
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
    fresh_material(qapp, window)
    before = stored_blocks(window)
    undo_steps = len(session._undo)
    session.solve()
    settled(qapp, window)
    pump(qapp)
    assert stored_blocks(window) == before
    assert len(session._undo) == undo_steps, "no plan change means no Undo step"
    assert not (_snack(window) and _action(window) == "UNDO"), "no Undo for a plan that could place nothing"


def test_plan_waits_for_a_failed_save_before_offering_undo(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    fresh_material(qapp, window)
    before = stored_blocks(window)
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "failed-save"}
    # The autosave tick would retry the failed save and finish it mid-test.
    window._autosave.stop()
    _bridge(window).week.plan()
    pump(qapp, 5)
    assert stored_blocks(window) == before
    assert session.message == "Saving your last change… Plan will work in a moment."
    assert not (_snack(window).startswith("Placed") and _action(window) == "UNDO")
