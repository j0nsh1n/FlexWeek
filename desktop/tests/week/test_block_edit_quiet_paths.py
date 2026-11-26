"""Quiet no-op paths for the Rust block and repeat edit decisions: `change_repeats` with no
change and `delete_block` for an id not in the week return without touching the week."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week
from desktop.tests.window_support import qapp  # noqa: F401


def test_change_repeats_with_no_change_returns_quietly(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    before = (deepcopy(session.blocks), deepcopy(session.repeats))
    undo, dirty = len(session._undo), session.dirty
    session.change_repeats(deepcopy(session.repeats), "no-op")
    assert session.blocks == before[0]
    assert session.repeats == before[1]
    assert (len(session._undo), session.dirty) == (undo, dirty)


def test_delete_block_with_an_id_not_in_the_week_returns_quietly(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    before = (deepcopy(session.blocks), deepcopy(session.repeats))
    undo, dirty = len(session._undo), session.dirty
    session.delete_block("missing")
    assert session.blocks == before[0]
    assert session.repeats == before[1]
    assert (len(session._undo), session.dirty) == (undo, dirty)
