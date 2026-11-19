"""Plan's Undo notice stays until it is used.

A second Plan with nothing new used to replace "Placed 1 of 1" and its Undo with "All your homework already
has a time." After Plan the notice keeps its Undo, and a re-plan offers Undo for the changes it placed.
Run on the Material week's snackbar.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from copy import deepcopy

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.real_surface

from PySide6.QtWidgets import QApplication

from desktop.native.material import bridge as bridge_module
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.planner.undo_support import MATERIAL_PLACED, planned_in_material
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _bridge, _click, _pump, _qml, _snack
from desktop.tests.window_support import qapp, settled  # noqa: F401

# An Undo notice stays at least this long.
ACTION_MS = 10_000


def undo_still_offered(window: NativeWindow) -> tuple[str, str]:
    return _snack(window), str(_bridge(window).property("snackAction"))


def test_plan_offers_undo_in_its_snackbar(qapp: QApplication, window: NativeWindow) -> None:
    planned_in_material(qapp, window)
    assert undo_still_offered(window) == (MATERIAL_PLACED, "UNDO")
    assert bridge_module.SNACK_MS >= ACTION_MS
    assert _bridge(window)._snack_timer.interval() >= ACTION_MS


def test_a_second_plan_with_the_disabled_button_keeps_the_undo_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = planned_in_material(qapp, window)
    plan = _qml(root, "planHomework")
    assert plan.property("enabled") is False, "nothing is left to place"
    _click(window, plan)
    settled(qapp, window)
    assert undo_still_offered(window) == (MATERIAL_PLACED, "UNDO")


def test_the_plan_key_with_nothing_to_do_keeps_the_undo_notice(qapp: QApplication, window: NativeWindow) -> None:
    planned_in_material(qapp, window)
    _bridge(window).plan()  # the P key's call
    settled(qapp, window)
    _pump(qapp)
    assert undo_still_offered(window) == (MATERIAL_PLACED, "UNDO")


def test_a_second_plan_with_nothing_to_do_starts_the_notices_time_over(
    qapp: QApplication, window: NativeWindow
) -> None:
    planned_in_material(qapp, window)
    timer = _bridge(window)._snack_timer
    timer.start(5_000)
    _bridge(window).plan()
    settled(qapp, window)
    assert undo_still_offered(window) == (MATERIAL_PLACED, "UNDO")
    assert timer.remainingTime() > 5_000


def test_a_plan_with_nothing_to_do_from_the_session_keeps_the_undo_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The session's own Plan (what every Plan control calls), not tied to one button."""
    planned_in_material(qapp, window)
    window.session.solve()
    settled(qapp, window)
    _pump(qapp)
    assert undo_still_offered(window) == (MATERIAL_PLACED, "UNDO")


def test_the_undo_on_the_snackbar_takes_the_plan_back(qapp: QApplication, window: NativeWindow) -> None:
    root = planned_in_material(qapp, window)
    session = window.session
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    settled(qapp, window)
    assert not any(b.get("start") for b in session.blocks if b.get("assignment_id") == "essay")


@pytest.mark.parametrize("mode", ["joined-save", "queued-save", "auto-split"])
def test_replan_offers_undo_for_the_changes_it_placed(
    qapp: QApplication, window: NativeWindow, mode: str
) -> None:
    session = window.session
    if mode == "auto-split":
        session.preferences = {**(session.preferences or {}), "auto_split": True}
    planned_in_material(qapp, window)
    before_edit = deepcopy(session.blocks)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    session.blocks = [{**b, "start": None} if b is essay else b for b in session.blocks]
    if mode == "queued-save":
        session.save()
        before_replan = deepcopy(session.blocks)
        session.solve(everything=True)
    else:
        session.save()
        settled(qapp, window)
        before_replan = deepcopy(session.blocks)
        if mode == "joined-save":
            session.solve(everything=True, join=True)
        else:
            _bridge(window).sheets.moreAction("replanAll")
    wait_until(
        qapp,
        lambda: not session.planning
        and not session.busy
        and not session.dirty
        and _snack(window).startswith("Placed")
        and _bridge(window).property("snackAction") == "UNDO",
        timeout=20,
        what="the re-plan's Undo notice",
    )
    settled(qapp, window)
    _bridge(window).undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, window)
    assert session.blocks == (before_edit if mode == "joined-save" else before_replan)
