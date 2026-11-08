# ruff: noqa: F811
"""The Material Unfinished sheet: it lists overdue homework, asks before a delete, and Find a time plans
through the session, with a preview first for homework that still has its deadline.

Expected words and values come from the Widgets sheet's wording and the week the fixtures build (the
clock at Thursday 19:00 in the week of Monday 2 November 2026).
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from desktop.native.widgets import PreviewDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheets import (  # noqa: E402,F401
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402


def test_unfinished_lists_overdue_homework_and_delete_asks_first(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    session = shell.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "lab-writeup",
            "title": "Lab write-up",
            "due": f"{session.week_start}T09:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    settle(qapp, shell)
    sheets.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    assert rows["unfinishedOpen"]["enabled"] is True
    assert rows["unfinishedOpen"]["detail"] != "None left"
    sheets.moreAction("unfinishedOpen")
    pump(qapp)
    assert sheets.kind == "unfinished"
    found = next(row for row in sheets.form["rows"] if row["id"] == "lab-writeup")
    assert found["title"] == "Lab write-up"
    assert found["plannable"] is True
    assert found["overdue"] is True
    assert found["detail"].startswith("45 min left")
    assert f"due Mon {monday.day} {monday.strftime('%b')}" in found["detail"]
    assert found["detail"].endswith("Overdue")
    assert find_named(shell._material_page.root, "planUnfinished-lab-writeup") is not None

    sheets.askDeleteUnfinished("lab-writeup")
    assert sheets.ask["title"] == "Delete homework"
    assert "Its times on the calendar go too, in every week." in sheets.ask["body"]
    sheets.answer("stay")
    assert "lab-writeup" in session.assignments
    sheets.askDeleteUnfinished("lab-writeup")
    sheets.answer("delete")
    wait_until(qapp, lambda: "lab-writeup" not in session.assignments)
    assert sheets.notice == "Deleted Lab write-up."
    settle(qapp, shell)


def test_unfinished_find_a_time_plans_overdue_homework_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    session = shell.session
    session.add_homework(
        {
            "id": "overdue-quiz",
            "title": "Overdue quiz",
            "due": f"{session.week_start}T08:00",
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settle(qapp, shell)
    sheets.openUnfinished()
    sheets.findTime("overdue-quiz")
    wait_until(
        qapp,
        lambda: any(item.get("assignment_id") == "overdue-quiz" for item in session.blocks),
    )
    settle(qapp, shell)


def _add_open_essay(qapp: QApplication, session) -> str:
    """Left from last week, due after the held Thursday clock, so Find a time still has minutes."""
    current = session.week_start
    previous = (date.fromisoformat(current) - timedelta(days=7)).isoformat()
    sunday = (date.fromisoformat(current) + timedelta(days=6)).isoformat()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    session.add_homework(
        {
            "id": "open-essay",
            "title": "Open essay",
            "due": f"{sunday}T21:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy)
    session.load_week(current)
    wait_until(qapp, lambda: session.week_start == current and not session.busy)
    return "open-essay"


def _block_ids(session) -> set[str]:
    return {item["id"] for item in session.blocks}


def test_unfinished_find_a_time_leaves_non_overdue_blocks_unchanged_until_accept(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Homework that still has a deadline must wait for the Widgets preview's Accept."""
    session = shell.session
    current = session.week_start
    try:
        assignment_id = _add_open_essay(qapp, session)
    finally:
        if session.week_start != current:
            session.load_week(current)
            wait_until(qapp, lambda: session.week_start == current and not session.busy)
    before = _block_ids(session)
    opened: list[str] = []
    assert assignment_id not in session._overdue_assignment_ids()
    assert session.remaining_for(assignment_id) >= 15, session.assignments.get(assignment_id)
    assert session.plan_unfinished(assignment_id)

    def cancel(dialog: PreviewDialog) -> int:
        opened.append(dialog.objectName())
        assert _block_ids(session) == before
        assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(PreviewDialog, "exec", cancel)
    sheets.openUnfinished()
    found = next(row for row in sheets.form["rows"] if row["id"] == assignment_id)
    assert found["overdue"] is False
    sheets.findTime(assignment_id)
    assert opened == ["stage3PreviewDialog"]
    assert _block_ids(session) == before
    assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)

    def accept(dialog: PreviewDialog) -> int:
        opened.append(dialog.objectName())
        assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PreviewDialog, "exec", accept)
    sheets.findTime(assignment_id)
    wait_until(
        qapp,
        lambda: any(item.get("assignment_id") == assignment_id for item in session.blocks),
    )
    assert opened == ["stage3PreviewDialog", "stage3PreviewDialog"]
    settle(qapp, shell)
