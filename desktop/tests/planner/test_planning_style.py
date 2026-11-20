# ruff: noqa: F811
"""The planning style: new homework gets a time as it is added (one Undo step) or waits for Plan my
homework, and the Plan button says what the style is. Driven through Material's Add homework sheet."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)
from desktop.tests.material_support import pump, qml  # noqa: E402
from desktop.tests.week.support_material_page import fresh_material  # noqa: E402


def _add_through_the_sheet(qapp: QApplication, window: NativeWindow) -> dict:
    fresh_material(qapp, window)
    sheets = window._material_page.bridge.sheets
    sheets.openHomework()
    sheets.setText("title", "Chemistry lab")
    pump(qapp, 20)
    sheets.save()
    session = window.session
    wait_until(qapp, lambda: any(item["title"] == "Chemistry lab" for item in session.assignments.values()))
    settled(qapp, window)
    wait_until(
        qapp,
        lambda: not session.busy
        and not session.dirty
        and not any(session.client._replies.values())
        and not getattr(session.client, "pending", 0),
        what="the add and its plan being answered",
    )
    return next(item for item in session.assignments.values() if item["title"] == "Chemistry lab")


def test_plan_it_as_i_add_it_gives_new_homework_a_time_in_one_undo_step(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "planning_style": "auto"}
    added = _add_through_the_sheet(qapp, window)
    sessions = [block for block in window.session.blocks if block.get("assignment_id") == added["id"]]
    assert sessions and all(block.get("start") for block in sessions), "placed without pressing Plan"
    window._material_page.bridge.undo()
    settled(qapp, window)
    assert added["id"] not in window.session.assignments, "one Undo takes back the homework and its time"
    assert not any(block.get("assignment_id") == added["id"] for block in window.session.blocks)


def test_by_default_new_homework_waits_for_plan_my_homework(qapp: QApplication, window: NativeWindow) -> None:
    added = _add_through_the_sheet(qapp, window)
    sessions = [block for block in window.session.blocks if block.get("assignment_id") == added["id"]]
    assert sessions and not any(block.get("start") for block in sessions)
    pump(qapp)
    assert qml(window._material_page.root, "planHomework").property("text") == "Plan my homework"


def test_placing_by_hand_turns_plan_into_suggest_times(qapp: QApplication, window: NativeWindow) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "planning_style": "manual"}
    root = fresh_material(qapp, window)
    window._material_page.publish()
    pump(qapp)
    assert qml(root, "planHomework").property("text") == "Suggest times"
    assert qml(root, "planHomework").property("accessName") == "Suggest times"
