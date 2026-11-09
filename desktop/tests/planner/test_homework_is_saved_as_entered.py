"""Homework comes back from the server as it was entered: notes, links and checklist after a reload, a
plain stamp for the time it was ticked off, and the day and due time it was dropped on."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import due_on, session_in_the_planned_week
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_notes_links_and_checklist_survive_a_reload(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    due = due_on(session, 4, "08:10")
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "due": due,
            "estimate_min": 60,
            "revision": 0,
            "notes": "Bring the printout",
            "links": [{"label": "Spec", "url": "https://example.com/spec"}],
            "checklist": [{"id": "step-1", "text": "Outline", "done": True}],
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session_id = next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab")
    session.add_homework(
        {
            **session.assignments["lab"],
            "notes": "Bring the printout and a pencil",
        }
    )
    assert next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab") == session_id
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.reload()
    wait_until(qapp, lambda: not session.busy and "lab" in session.assignments)
    item = session.assignments["lab"]
    assert item["due"] == due
    assert item["notes"] == "Bring the printout and a pencil"
    assert item["links"] == [{"label": "Spec", "url": "https://example.com/spec"}]
    assert item["checklist"][0]["done"] is True
    assert next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab") == session_id


def test_completing_homework_stores_a_stamp_without_a_time_zone(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_homework(
        {
            "id": "quiz",
            "title": "Quiz",
            "due": due_on(session, 2),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.complete_homework("quiz")
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    item = session.assignments["quiz"]
    assert item["completed"] is True
    assert item["completed_at"] == clock.now().strftime("%Y-%m-%dT%H:%M")


def test_homework_dropped_on_a_day_keeps_its_exact_due_time_and_that_day(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.arm_category("assignments")
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "chem",
            "title": "Chemistry lab report",
            "due": due,
            "estimate_min": 90,
            "category": "assignments",
            "revision": 0,
        },
        days=[2],
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = session.blocks[0]
    assert block["kind"] == "flexible"
    assert block["days"] == [2]
    assert block.get("start") in {None, ""}
    assert block["duration_min"] == 90
    assert session.assignments["chem"]["due"] == due
