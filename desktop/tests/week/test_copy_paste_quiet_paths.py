"""Quiet no-op paths for the Rust clipboard decisions: an empty last week offers no copy
rows, pasting or copying a day with nowhere to go says so instead of crashing, and the
PyO3 bindings refuse malformed JSON shapes."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime

import flexweek_engine
import pytest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_fixed_copy_rows_with_nothing_last_week_offers_nothing(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    assert session._fixed_copy_rows(None) is None
    assert session._fixed_copy_rows({}) is None
    assert session._fixed_copy_rows({"blocks": None}) is None
    assert session._fixed_copy_rows({"blocks": []}) is None


def test_copy_last_week_empty_says_nothing_to_copy(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    said: list[str] = []
    session.status.connect(said.append)
    got: list[list[dict] | None] = []
    session.copy_last_week_fixed_rows(got.append)
    wait_until(qapp, lambda: bool(got) and not session.busy)
    assert got == [None]
    assert "There's nothing to copy from last week yet." in said


def test_paste_with_no_destination_says_so_quietly(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    assert session.copy_block("soccer", 0, say=False) is True
    session.select_block(None, None)
    # Far from the open week, so neither the planner day nor today names a destination.
    clock.set(datetime(2026, 12, 21, 12, 0))
    said: list[str] = []
    session.status.connect(said.append)
    before = (deepcopy(session.blocks), deepcopy(session.clipboard))
    assert session.paste_destination() is None
    assert session.copy_day() is False
    assert session.paste_proposals() is None
    assert "Select a block or open Day view before copying a day from this week." in said
    assert "Select a block or open Day view before pasting into this week." in said
    assert session.blocks == before[0]
    assert session.clipboard == before[1]


def test_stale_selection_falls_through_to_today(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.select_block("missing", 1)
    assert session.paste_destination() == (0, None)


def test_copy_bindings_refuse_wrong_json_shapes() -> None:
    with pytest.raises(TypeError):
        flexweek_engine.fixed_copy_rows_json("[]", "2026-09-21", [])
    with pytest.raises(TypeError):
        flexweek_engine.copy_empty_words_json("[]")
    with pytest.raises(TypeError):
        flexweek_engine.date_problem_json(
            "soccer", "2026-09-24", "2026-09-22", "2026-09-21", "2026-09-21",
            3, 1, "[]", None, None, None, "{}", "2026-09-23", 480, 15,
        )
    with pytest.raises(TypeError):
        flexweek_engine.date_problem_json(
            "soccer", "2026-09-24", "2026-09-22", "2026-09-21", "2026-09-21",
            3, 1, "null", None, None, None, "[]", "2026-09-23", 480, 15,
        )
    with pytest.raises(TypeError):
        flexweek_engine.relocate_json(
            "soccer", 3, 1, "2026-09-21", "2026-09-21",
            '{"blocks": []}', "null", "[]", "this week", "made-1",
        )
    with pytest.raises(TypeError):
        flexweek_engine.paste_destination_json(
            "{}", "{}", None, None, "week", 0, "2026-09-21", "2026-09-23", "2026-09-21",
        )
    with pytest.raises(TypeError):
        flexweek_engine.paste_destination_json(
            "[]", "[]", None, None, "week", 0, "2026-09-21", "2026-09-23", "2026-09-21",
        )
    with pytest.raises(TypeError):
        flexweek_engine.clipboard_day_json("[]", "[]", 2, "2026-09-21", [])
    with pytest.raises(TypeError):
        flexweek_engine.paste_ready_json(
            "[]", 2, None, "[]", "{}", None, None, "week", 0, "2026-09-21", "2026-09-23", "2026-09-21",
        )
    with pytest.raises(TypeError):
        flexweek_engine.paste_ready_json(
            "{}", 2, None, "{}", "{}", None, None, "week", 0, "2026-09-21", "2026-09-23", "2026-09-21",
        )
    with pytest.raises(TypeError):
        flexweek_engine.paste_ready_json(
            "{}", 2, None, "[]", "[]", None, None, "week", 0, "2026-09-21", "2026-09-23", "2026-09-21",
        )
