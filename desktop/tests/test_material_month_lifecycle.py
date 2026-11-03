# ruff: noqa: F811
"""Permanent regression tests for Material month preview lifecycle and account isolation."""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from shiboken6 import delete

from desktop.native.client import ApiError
from desktop.native.material.bridge_settings import PassiveMonthBridge
from desktop.tests.test_material_account_setup import (
    create,
    launches,  # noqa: F401
    pump,
    qapp,  # noqa: F401
    settle,
    sign_out,
    skip_setup,
    through_recovery,
    wait_until,
)
from desktop.tests.test_material_static_audit import _bridge, _named, _panel

_lives: list[QObject] = []


@pytest.fixture(autouse=True)
def dispose_live(no_window_is_left_for_the_garbage_collector: Any) -> Any:
    yield
    while _lives:
        delete(_lives.pop())


class Live(QObject):
    changed = Signal()

    def __init__(self, session: Any) -> None:
        super().__init__()
        self.session = session
        _lives.append(self)

    def _session(self) -> Any:
        return self.session


class Held:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def request(self, *args: Any) -> None:
        self.calls.append(args)


def rig(qapp: Any) -> tuple[Any, Held, Live, PassiveMonthBridge]:
    held = Held()
    session = SimpleNamespace(
        account={"id": "A"},
        selected_month=None,
        month_data=None,
        preferences={},
        week_start=None,
        unsaved_weeks=lambda: {},
        today_iso=lambda: "2026-11-03",
        _month_cache={},
        client=held,
    )
    live = Live(session)
    preview = PassiveMonthBridge(live, live)
    return session, held, live, preview


def snap(month: str = "2026-11", title: str = "A personal homework") -> dict[str, Any]:
    return {
        "month": month,
        "days": [
            {
                "date": f"{month}-23",
                "in_month": True,
                "blocks": [
                    {
                        "id": "personal",
                        "title": title,
                        "category": "homework",
                        "start": "17:00",
                        "duration_min": 75,
                        "completed": True,
                    }
                ],
            }
        ],
    }


def totals(preview: PassiveMonthBridge) -> tuple[int, int]:
    return sum(r["plannedMin"] for r in preview.cellRows), sum(r["completedMin"] for r in preview.cellRows)


def state(s: Any) -> Any:
    return copy.deepcopy(
        (
            s.planner_view,
            s.selected_day,
            s.selected_month,
            s.month_data,
            s.preferences,
            s.blocks,
            s.assignments,
            s.built_week(),
            s.unsaved_weeks(),
        )
    )


def test_target_month_change_drops_dedicated_snapshot(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    assert totals(preview) == (75, 75)
    session.selected_month = "2026-12"
    session.month_data = snap("2026-12", "December homework")
    live.changed.emit()
    months = {r["iso"][:7] for r in preview.cellRows if r["inMonth"]}
    assert months == {"2026-12"}, "December target renders November after dedicated November GET"


def test_logout_clears_dedicated_snapshot_and_rows(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    assert totals(preview) == (75, 75)
    session.account = None
    session._month_cache.clear()
    live.changed.emit()
    assert preview.dates.rowCount() == 0 and preview._preview_snapshot is None


def test_same_month_account_change_uses_new_account_cache(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    session.account = {"id": "B"}
    session._month_cache = {("B", "2026-11"): {"month": "2026-11", "days": []}}
    live.changed.emit()
    assert totals(preview) == (0, 0), "Account B sees account A homework despite B-keyed empty cache"


def test_old_error_cannot_poison_new_success(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    old = held.calls[0]
    session.selected_month = "2026-12"
    live.changed.emit()
    new = held.calls[1]
    new[3](snap("2026-12"))
    old[4](ApiError(503, "old November failure"))
    assert not preview._load_error, "Old November error overwrites successful December state"


def test_older_success_cannot_win_nov_dec_nov(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    old_november = held.calls[0]
    session.selected_month = "2026-12"
    live.changed.emit()
    session.selected_month = "2026-11"
    live.changed.emit()
    newest_november = held.calls[2]
    newest_november[3]({"month": "2026-11", "days": []})
    assert totals(preview) == (0, 0)
    old_november[3](snap())
    assert totals(preview) == (0, 0), (
        "Older November request overwrites newer November success after Nov-Dec-Nov navigation"
    )


def test_cache_only_account_switch_positive_control(qapp: Any) -> None:
    held = Held()
    session = SimpleNamespace(
        account={"id": "A"},
        selected_month=None,
        month_data=None,
        preferences={},
        week_start=None,
        unsaved_weeks=lambda: {},
        today_iso=lambda: "2026-11-03",
        _month_cache={("A", "2026-11"): snap()},
        client=held,
    )
    live = Live(session)
    preview = PassiveMonthBridge(live, live)
    assert totals(preview) == (75, 75) and not held.calls
    session.account = {"id": "B"}
    session._month_cache = {("B", "2026-11"): {"month": "2026-11", "days": []}}
    live.changed.emit()
    assert totals(preview) == (0, 0) and not held.calls


def test_no_extra_get_before_settings_preview(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    seen: list[tuple[str, str, str, str]] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            seen.append((path, ok.__qualname__, _bridge(win)._screen, s.planner_view))
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "no_extra_get_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    # Live planner is on week, no month history
    assert s.planner_view == "week" and s.selected_month is None and s.month_data is None

    # Before settings or advanced preview is opened, passive month bridge must NOT issue an eager GET
    preview_gets = [c for c in seen if "PassiveMonthBridge" in c[1]]
    assert len(preview_gets) == 0, (
        f"Expected 0 PassiveMonthBridge GETs before Settings, got {len(preview_gets)}: {preview_gets}"
    )


def test_real_cold_held_get_failure_and_reopen(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    seen: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            seen.append((path, ok.__qualname__, _bridge(win)._screen, s.planner_view))
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "cold_held_failure_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    before = state(s)
    preview = _panel(win)._preview._passive_month

    # Open Settings -> Advanced -> Month preview
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    root = win._material_page.root
    month = _named(_named(root, "settingsPreviewMonth")[0], "materialMonth")[0]
    numbers = _named(month, "monthDayNumber")
    headers = _named(month, "monthWeekday")

    # Calendar structure is populated even while loading
    assert preview.dates.rowCount() >= 28 and len(numbers) == preview.dates.rowCount()
    assert preview.weekdays.rowCount() == 7 and len(headers) == 7
    assert all(str(x.property("text")) for x in numbers)
    assert state(s) == before
    assert preview.loading, "Month preview should indicate loading while request is in flight"

    # Status banner shows loading
    status_banner = _named(root, "monthPreviewStatus")[0]
    assert status_banner.isVisible()

    # Fail the held requests with 503
    for req in list(held):
        req[4](ApiError(503, "review month service unavailable"))
    held.clear()
    QTest.qWait(100)

    # Verify failure state and UI indication
    assert not preview.loading
    assert preview.loadError == "review month service unavailable"
    assert status_banner.isVisible()
    status_text = _named(root, "monthPreviewStatusText")[0]
    assert str(status_text.property("text")) == "review month service unavailable"
    retry_btn = _named(root, "monthPreviewRetry")[0]
    assert retry_btn.isVisible()
    assert state(s) == before

    # Reopen Advanced and switch to Month: resets failure and triggers retry
    panel.closeAdvanced()
    panel.openAdvanced()
    panel.setPreviewView("week")
    panel.setPreviewView("month")
    QTest.qWait(100)

    # Should have triggered a retry request in held
    assert len(held) >= 1, "Reopen should initiate retry request"
    assert preview.loading

    # Settle the retry with successful month response
    held[-1][3]({"month": "2026-11", "days": []})
    QTest.qWait(100)

    assert not preview.loading
    assert preview.loadError == ""
    reopened_banner = _named(win._material_page.root, "monthPreviewStatus")[0]
    assert not reopened_banner.isVisible()
    assert preview.dates.rowCount() >= 28
    assert state(s) == before


def test_real_account_replacement_does_not_keep_personal_counts(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    create(qapp, win, "cold_owner_a")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    preview = _panel(win)._preview._passive_month

    # Save real locked homework on current week (Nov 2-8) and future week (Nov 16-22)
    s.add_block(
        {
            "id": "owner-a-personal",
            "title": "Owner A private homework",
            "kind": "locked",
            "category": "homework",
            "start": "17:00",
            "duration_min": 75,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    print("BEFORE_SAVE_DIRTY", s.dirty, "BUSY", s.busy, "ACCOUNT", s.account)
    s.save()
    print("AFTER_SAVE_PENDING", s.pending_save, "BUSY", s.busy)
    settle(qapp, win)
    print("AFTER_SETTLE_BUSY", s.busy, "DIRTY", s.dirty)

    home_week = s.week_start
    future = (date.fromisoformat(home_week) + timedelta(days=14)).isoformat()
    print("LOADING_FUTURE", future)
    s.load_week(future)
    settle(qapp, win)
    print("LOADED_FUTURE_WEEK_START", s.week_start, "BUSY", s.busy)
    s.add_block(
        {
            "id": "owner-a-future",
            "title": "Owner A private future homework",
            "kind": "locked",
            "category": "homework",
            "start": "17:00",
            "duration_min": 75,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    print("BEFORE_SECOND_SAVE_DIRTY", s.dirty, "BUSY", s.busy)
    s.save()
    print("AFTER_SECOND_SAVE_PENDING", s.pending_save, "BUSY", s.busy)
    settle(qapp, win)
    print("AFTER_SECOND_SETTLE_BUSY", s.busy, "DIRTY", s.dirty)
    s.load_week(home_week)
    settle(qapp, win)
    s._month_cache.clear()

    # Open Settings -> Advanced -> Month preview
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    wait_until(
        qapp,
        lambda: preview._preview_snapshot is not None,
        timeout=5.0,
    )

    old_account = s.account["id"]
    old_total = totals(preview)
    assert any(r["iso"] == future and r["plannedMin"] == 75 for r in preview.cellRows)
    assert old_total[0] > 7 * 75  # Full month has planned minutes from both weeks

    # Sign out
    sign_out(qapp, win)
    pump(qapp)

    # Immediately on sign out, preview must be cleared
    assert preview.dates.rowCount() == 0
    assert totals(preview) == (0, 0)
    assert preview._preview_snapshot is None

    # Sign in as empty Account B
    create(qapp, win, "cold_owner_b")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    settle(qapp, win)

    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    rows = preview.cellRows
    private = [r["iso"] for r in rows if "Owner A private" in json.dumps(r)]
    assert s.account["id"] != old_account
    assert not s.blocks
    assert not private and totals(preview) == (0, 0), (
        "New account B displays previous account A full-month homework/counts"
    )
