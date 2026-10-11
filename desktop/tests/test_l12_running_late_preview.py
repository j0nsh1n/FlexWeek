# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import LateDialog
from desktop.tests.logic_support import qapp, server, settled, signed_in, wait_until  # noqa: F401


def _dialog() -> LateDialog:
    set_clock_24h(False)
    dialog = LateDialog(None, "Starting from 5:00 PM today (Monday).")
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [
                {"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}
            ],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    return dialog


def test_running_late_preview_shows_day_and_both_full_ranges(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    item = dialog.changes.item(0)
    assert item.text() == "Mon 4:45–5:45 PM → Mon 5:15–6:15 PM"
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Late test, moves from Monday 4:45 to 5:45 PM to Monday 5:15 to 6:15 PM"
    )
    assert dialog.summary.text() == "1 task moves"
    dialog.show_trace({"moves": [], "placed": [], "unplaced": [{"id": "lost", "title": "Lost"}]}, {})
    assert dialog.summary.text() == "1 task no longer fits"
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_names_and_bolds_a_changed_day(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    trace = {
        "moves": [
            {
                "block_id": "late-test",
                "from_day": 0,
                "from_start": "16:45",
                "to_day": 1,
                "to_start": "17:15",
            }
        ],
        "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}],
        "unplaced": [],
    }
    dialog.show_trace(trace, {"late-test": "Late test"})
    item = dialog.changes.item(0)
    assert "Tue" in item.text()
    assert "<b>Tue</b>" in dialog.changes.itemWidget(item).text()
    assert "different day" in item.data(Qt.ItemDataRole.AccessibleTextRole)
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_uses_singular_plural_and_omits_zero_counts(qapp: QApplication) -> None:  # noqa: F811
    dialog = _dialog()
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                },
                {
                    "block_id": "other",
                    "from_day": 0,
                    "from_start": "18:00",
                    "to_day": 0,
                    "to_start": "18:15",
                },
            ],
            "placed": [
                {"id": "late-test", "title": "Late test", "duration_min": 60},
                {"id": "other", "title": "Other", "duration_min": 60},
            ],
            "unplaced": [{"id": "lost", "title": "Lost"}],
        },
        {"late-test": "Late test", "other": "Other"},
    )
    assert dialog.summary.text() == "2 tasks move · 1 task no longer fits"
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60}],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    assert dialog.summary.text() == "1 task moves"
    set_clock_24h(True)
    dialog.close()


def _plan_at_monday_five(qapp: QApplication, server, username: str, *, everything: bool) -> list[dict]:
    session = signed_in(qapp, server.origin, username, create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    monday = datetime.fromisoformat(session.week_start)
    held = monday + timedelta(hours=17)
    session.now_ms = lambda: int(held.timestamp() * 1000)
    session.add_homework(
        {
            "id": "l12-floor-homework",
            "title": "L12 floor homework",
            "estimate_min": 60,
            "revision": 0,
            "due": (monday.date() + timedelta(days=3)).isoformat() + "T23:59",
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, session)
    session.solve(everything=everything)
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled(qapp, session)
    return [block for block in session.blocks if block.get("assignment_id") == "l12-floor-homework"]


def _assert_not_before_monday_five(blocks: list[dict]) -> None:
    for block in blocks:
        if not block.get("start"):
            continue
        day = min(block.get("days") or [0])
        hour, minute = map(int, block["start"].split(":"))
        assert (day, hour * 60 + minute) >= (0, 17 * 60), block


def test_plan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, server) -> None:
    blocks = _plan_at_monday_five(qapp, server, "l12_plan_floor", everything=False)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_replan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, server) -> None:
    blocks = _plan_at_monday_five(qapp, server, "l12_replan_floor", everything=True)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)
