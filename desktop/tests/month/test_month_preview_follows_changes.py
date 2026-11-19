# ruff: noqa: F811
"""The month preview in Settings > Advanced keeps up with what the student does: a moved block, an
undo, a save and a plan change its counts without reopening it, and a reply that was on its way
before a save never lands in the session's month cache."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.material_support import show_material  # noqa: E402
from desktop.tests.month.support_material_month import (  # noqa: E402
    hold_month_requests,
    idle,
    open_month_preview,
    snap,
    totals,
)
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-preview-changes"])


def test_moving_a_block_to_another_week_and_undoing_it_updates_both_weeks_in_the_preview(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    show_material(qapp, window)

    # Homework with a fixed time on Tuesday 3 November, in the account's first week.
    session.add_homework(
        {
            "id": "essay_id",
            "title": "November HW",
            "due": "2026-11-22T23:59",
            "estimate_min": 60,
            "fixed_at": {"day": 1, "start": "17:00"},
        }
    )
    block_id = next(b for b in session.blocks if b.get("assignment_id") == "essay_id")["id"]
    session.save()
    wait_until(qapp, lambda: idle(window))

    session.open_month("2026-11")
    wait_until(qapp, lambda: session.month_data is not None and not session.busy)
    on_the_third = [
        b["id"]
        for d in session.month_data.get("days", [])
        if d.get("date") == "2026-11-03"
        for b in d.get("blocks", [])
    ]
    assert block_id in on_the_third, "Initial block not loaded in real month_data"

    assert session.move_to_date(block_id, "2026-11-03", "2026-11-10") is True
    wait_until(qapp, lambda: idle(window))

    _root, _settings, preview = open_month_preview(qapp, window)
    wait_until(qapp, lambda: not preview.loading and len(preview.cellRows) > 0)

    # The moved block shows on its new date and is gone from the old one.
    nov_03 = next(r for r in preview.cellRows if r["iso"] == "2026-11-03")
    nov_10 = next(r for r in preview.cellRows if r["iso"] == "2026-11-10")
    assert nov_03["plannedMin"] == 0 and len(nov_03["chipTexts"]) == 0, (
        f"3 November should have 0 min after the move, got {nov_03['plannedMin']}"
    )
    assert nov_10["plannedMin"] == 60 and len(nov_10["chipTexts"]) == 1, (
        f"10 November should have 60 min after the move, got {nov_10['plannedMin']}"
    )

    session.undo()
    wait_until(qapp, lambda: idle(window))
    wait_until(qapp, lambda: not preview.loading)

    nov_03_undone = next(r for r in preview.cellRows if r["iso"] == "2026-11-03")
    nov_10_undone = next(r for r in preview.cellRows if r["iso"] == "2026-11-10")
    assert nov_03_undone["plannedMin"] == 60 and len(nov_03_undone["chipTexts"]) == 1, (
        f"3 November should have 60 min after the undo, got {nov_03_undone['plannedMin']}"
    )
    assert nov_10_undone["plannedMin"] == 0 and len(nov_10_undone["chipTexts"]) == 0, (
        f"10 November should have 0 min after the undo, got {nov_10_undone['plannedMin']}"
    )


def test_after_undo_the_preview_shows_the_new_counts_without_reopening(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    show_material(qapp, window)
    session.add_block(
        {
            "id": "hw_undo",
            "title": "Physics HW",
            "kind": "flexible",
            "category": "homework",
            "start": "17:00",
            "duration_min": 45,
            "days": [1],
        }
    )
    session.save()
    wait_until(qapp, lambda: idle(window))

    _root, _settings, preview = open_month_preview(qapp, window)
    wait_until(qapp, lambda: not preview.loading and len(preview.cellRows) > 0)
    assert totals(preview) == (45, 0)

    session.undo()
    wait_until(qapp, lambda: idle(window))
    wait_until(qapp, lambda: not preview.loading)

    assert totals(preview) == (0, 0)




def test_a_late_reply_after_a_save_does_not_land_in_the_cache(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    held = hold_month_requests(window)
    show_material(qapp, window)
    wait_until(qapp, lambda: idle(window))
    key = (str(session.account["id"]), "2026-11")

    # The session's own fetch of the month.
    held.clear()
    session.selected_month = "2026-11"
    session.planner_view = "month"
    session._fetch_month()
    assert len(held) == 1
    fetch_call = held[0]

    # A save runs, which clears the cache and starts a new generation.
    session.add_block(
        {
            "id": "b1",
            "title": "Block 1",
            "kind": "flexible",
            "category": "homework",
            "start": "17:00",
            "duration_min": 60,
            "days": [1],
        }
    )
    session.save()
    wait_until(qapp, lambda: idle(window))

    # The reply from before the save arrives late.
    stale_data = snap("2026-11", "Stale fetch homework")
    fetch_call[3](stale_data)
    assert key not in session._month_cache, "Late _fetch_month reply landed in the cache after save"

    # The session's prefetch of the open week's month.
    held.clear()
    session._month_prefetching.clear()
    session._prefetch_open_week_month()
    assert len(held) == 1
    prefetch_call = held[0]

    session.add_block(
        {
            "id": "b2",
            "title": "Block 2",
            "kind": "flexible",
            "category": "homework",
            "start": "18:00",
            "duration_min": 60,
            "days": [2],
        }
    )
    session.save()
    wait_until(qapp, lambda: idle(window))

    prefetch_call[3](stale_data)
    assert key not in session._month_cache, (
        "Late _prefetch_open_week_month reply landed in session._month_cache after save"
    )
