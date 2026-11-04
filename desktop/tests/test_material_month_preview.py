# ruff: noqa: F811
"""Tests for month preview correctness in Settings Look preview (FIX-SPEC v1.3 PR 3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtTest import QTest
from shiboken6 import delete

from desktop.native.client import ApiError
from desktop.native.material.bridge_settings import PassiveMonthBridge
from desktop.tests.test_material_account_setup import (
    create,
    launches,  # noqa: F401
    pump,
    qapp,  # noqa: F401
    skip_setup,
    through_recovery,
    wait_until,
)
from desktop.tests.test_material_month_lifecycle import snap, totals
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


class Emitter(QObject):
    week_changed = Signal()
    account_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        _lives.append(self)


class Held:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def request(self, *args: Any) -> None:
        self.calls.append(args)


def rig(qapp: Any) -> tuple[Any, Held, Live, PassiveMonthBridge]:
    held = Held()
    emitter = Emitter()
    session = SimpleNamespace(
        account={"id": "A"},
        selected_month=None,
        month_data=None,
        preferences={},
        week_start=None,
        unsaved_weeks=lambda: {},
        today_iso=lambda: "2026-11-03",
        _month_cache={},
        _month_gen=0,
        client=held,
        week_changed=emitter.week_changed,
        account_changed=emitter.account_changed,
    )
    live = Live(session)
    preview = PassiveMonthBridge(live, live)
    return session, held, live, preview


def test_real_session_move_between_weeks_refetches_month_preview_for_both_weeks_and_undo(
    qapp: Any, launches: Any
) -> None:
    win = launches.launch()
    s = win.session
    create(qapp, win, "move_undo_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    # Add homework with fixed time on Tuesday of week 1 (2026-11-03)
    s.add_homework(
        {
            "id": "essay_id",
            "title": "November HW",
            "due": "2026-11-22T23:59",
            "estimate_min": 60,
            "fixed_at": {"day": 1, "start": "17:00"},
        }
    )
    hw_block = next(b for b in s.blocks if b.get("assignment_id") == "essay_id")
    block_id = hw_block["id"]
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Load November on the real Month screen
    s.open_month("2026-11")
    wait_until(qapp, lambda: s.month_data is not None and not s.busy)
    print("MONTH_DATA DAYS:")
    for d in s.month_data.get("days", []):
        if d.get("blocks"):
            print("  ", d.get("date"), d.get("blocks"))
    has_block = any(
        b["id"] == block_id
        for d in s.month_data.get("days", [])
        if d.get("date") == "2026-11-03"
        for b in d.get("blocks", [])
    )
    assert has_block, "Initial block not loaded in real month_data"

    # Move block from 2026-11-03 to 2026-11-10 through real session call
    ok = s.move_to_date(block_id, "2026-11-03", "2026-11-10")
    assert ok is True
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Open Settings Month preview
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    preview = panel._preview._passive_month
    wait_until(qapp, lambda: not preview.loading and len(preview.cellRows) > 0)

    # Shows the moved block new week and count for BOTH weeks
    nov_03 = next(r for r in preview.cellRows if r["iso"] == "2026-11-03")
    nov_10 = next(r for r in preview.cellRows if r["iso"] == "2026-11-10")
    assert nov_03["plannedMin"] == 0 and len(nov_03["chipTexts"]) == 0, (
        f"Week 1 should have 0 min after move, got {nov_03['plannedMin']}"
    )
    assert nov_10["plannedMin"] == 60 and len(nov_10["chipTexts"]) == 1, (
        f"Week 2 should have 60 min after move, got {nov_10['plannedMin']}"
    )

    # Undo through real session call
    s.undo()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)
    wait_until(qapp, lambda: not preview.loading)

    # Shows counts restored for BOTH weeks
    nov_03_undo = next(r for r in preview.cellRows if r["iso"] == "2026-11-03")
    nov_10_undo = next(r for r in preview.cellRows if r["iso"] == "2026-11-10")
    assert nov_03_undo["plannedMin"] == 60 and len(nov_03_undo["chipTexts"]) == 1, (
        f"Week 1 should have 60 min after undo, got {nov_03_undo['plannedMin']}"
    )
    assert nov_10_undo["plannedMin"] == 0 and len(nov_10_undo["chipTexts"]) == 0, (
        f"Week 2 should have 0 min after undo, got {nov_10_undo['plannedMin']}"
    )


def test_failed_request_clears_on_new_generation_and_asks_again_after_save(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "fail_refetch_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    preview = _panel(win)._preview._passive_month
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    assert len(held) >= 1
    # Preview GET fails with 503
    held[-1][4](ApiError(503, "Service unavailable"))
    QTest.qWait(100)

    assert not preview.loading
    assert preview.loadError == "Service unavailable"
    initial_requests = len(held)

    # Real save completes
    s.add_block(
        {
            "id": "new_block",
            "title": "Math HW",
            "kind": "flexible",
            "category": "homework",
            "start": "16:00",
            "duration_min": 45,
            "days": [2],
        }
    )
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)
    QTest.qWait(100)

    # Preview asks again without pressing Retry
    assert len(held) > initial_requests, "Preview did not ask again after save cleared failed state"
    assert preview.loading
    # Successful month response
    held[-1][3](snap("2026-11", "Math HW"))
    wait_until(qapp, lambda: not preview.loading)
    assert preview.loadError == ""
    assert totals(preview) == (120, 75)


def test_after_undo_the_preview_shows_the_new_counts_without_reopening(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    create(qapp, win, "real_undo_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    # Add block and save
    s.add_block(
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
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Open Settings Month preview
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    preview = panel._preview._passive_month
    wait_until(qapp, lambda: not preview.loading and len(preview.cellRows) > 0)
    assert totals(preview) == (45, 0)

    # Drive real Undo
    s.undo()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)
    wait_until(qapp, lambda: not preview.loading)

    # Shows new counts (0, 0) without reopening
    assert totals(preview) == (0, 0)


def test_after_a_save_and_plan_the_preview_asks_again(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "real_save_plan_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    preview = panel._preview._passive_month
    QTest.qWait(180)

    assert len(held) >= 1
    held[-1][3](snap("2026-11"))
    wait_until(qapp, lambda: not preview.loading)
    assert preview._preview_snapshot is not None
    count_before = len(held)

    # Drive real save action
    s.add_block(
        {
            "id": "save_blk",
            "title": "Art",
            "kind": "flexible",
            "category": "homework",
            "start": "15:00",
            "duration_min": 30,
            "days": [3],
        }
    )
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Preview asks again after real save
    assert len(held) > count_before, "Preview did not ask again after real save"
    assert preview.loading
    held[-1][3](snap("2026-11", "Art"))
    wait_until(qapp, lambda: not preview.loading)

    # Drive real plan action
    count_before = len(held)
    s.add_homework(
        {
            "id": "hw_plan",
            "title": "Bio report",
            "due": "2026-11-08T23:59",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)
    s.solve(everything=True)
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Preview asks again after real plan
    assert len(held) > count_before, "Preview did not ask again after real plan"


def test_a_late_reply_after_a_save_does_not_land_in_the_cache(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "late_reply_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    key = (str(s.account["id"]), "2026-11")

    # 1. Controller path: _fetch_month
    held.clear()
    s.selected_month = "2026-11"
    s.planner_view = "month"
    s._fetch_month()
    assert len(held) == 1
    fetch_call = held[0]

    # Real save runs, bumping _month_gen and clearing _month_cache
    s.add_block(
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
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Late reply from pre-save _fetch_month arrives
    stale_data = snap("2026-11", "Stale fetch homework")
    fetch_call[3](stale_data)

    # Must NOT land in session._month_cache
    assert key not in s._month_cache, "Late _fetch_month reply landed in session._month_cache after save"

    # 2. Controller path: _prefetch_open_week_month
    held.clear()
    s._month_prefetching.clear()
    s._prefetch_open_week_month()
    assert len(held) == 1
    prefetch_call = held[0]

    # Another real save runs
    s.add_block(
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
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    # Late reply from prefetch arrives
    prefetch_call[3](stale_data)

    # Must NOT land in session._month_cache
    assert key not in s._month_cache, (
        "Late _prefetch_open_week_month reply landed in session._month_cache after save"
    )


def test_a_late_error_after_a_month_switch_clears_loading_for_the_new_month_only(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    nov_call = held.calls[0]
    assert preview.loading

    # Switch month to December
    session.selected_month = "2026-12"
    live.changed.emit()
    assert len(held.calls) == 2
    dec_call = held.calls[1]
    assert preview.loading

    # Late error arrives for November
    nov_call[4](ApiError(500, "Nov server error"))

    # Must NOT clear loading because December is still loading
    assert preview.loading, "Late error for old month cleared loading for new month"
    assert preview.loadError == ""

    # Error arrives for December (the new month)
    dec_call[4](ApiError(503, "Dec server error"))

    # Now loading is cleared and error is set
    assert not preview.loading
    assert preview.loadError == "Dec server error"


def test_every_early_return_of_the_current_request_clears_loading(qapp: Any) -> None:
    # 1. ok: current_session is None
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    live.session = None
    emitted: list[bool] = []
    preview.changed.connect(lambda: emitted.append(True))
    call[3](snap())
    assert not preview.loading
    assert len(emitted) > 0, "Early return 1 did not emit changed"

    # 2. ok: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = {"id": "OTHER"}
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[3](snap())
    assert not preview.loading
    assert len(emitted) > 0, "Early return 2 did not emit changed"

    # 3. ok: invalid payload or mismatched month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[3]({"month": "2026-12", "days": []})
    assert not preview.loading
    assert len(emitted) > 0, "Early return 3 did not emit changed"

    # 4. err: current_session is None
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    live.session = None
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 4 did not emit changed"

    # 5. err: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = None
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 5 did not emit changed"

    # 6. err: self._target_month() != target_month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.selected_month = "2026-12"
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 6 did not emit changed"


def test_retry_works_by_click_through_the_shield(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "retry_click_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    preview = _panel(win)._preview._passive_month
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    assert len(held) >= 1
    held[-1][4](ApiError(503, "Service unavailable"))
    QTest.qWait(100)

    root = win._material_page.root
    retry_btn = _named(root, "monthPreviewRetry")[0]
    assert retry_btn.isVisible()
    assert preview.loadError == "Service unavailable"

    initial_requests = len(held)

    # Click directly on Retry through the shield
    center = retry_btn.mapToScene(QPointF(retry_btn.width() / 2, retry_btn.height() / 2))
    quick = win._material_page._quick
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(center.x()), int(center.y())),
    )
    pump(qapp)
    QTest.qWait(100)

    assert len(held) > initial_requests, "Clicking Retry did not trigger a new request"
    assert preview.loading


def test_retry_works_by_tab_and_space(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "retry_keyboard_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    preview = _panel(win)._preview._passive_month
    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    assert len(held) >= 1
    held[-1][4](ApiError(503, "Failed to load"))
    QTest.qWait(100)

    root = win._material_page.root
    retry_btn = _named(root, "monthPreviewRetry")[0]
    assert retry_btn.isVisible()
    assert retry_btn.property("activeFocusOnTab") is True
    acc_name = retry_btn.property("Accessible.name") or retry_btn.property("accessName")
    assert acc_name == "Retry loading the month preview"

    quick = win._material_page._quick
    preview_view = _named(root, "previewView")[0]
    preview_view.forceActiveFocus()
    pump(qapp)
    assert preview_view.property("activeFocus") is True

    # Reach Retry by Tab presses (no forceActiveFocus on Retry)
    for _ in range(10):
        if quick.quickWindow().activeFocusItem() is retry_btn:
            break
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        pump(qapp)

    assert quick.quickWindow().activeFocusItem() is retry_btn, "Retry button could not be reached via Tab"

    initial_requests = len(held)
    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp)
    QTest.qWait(100)

    assert len(held) > initial_requests, "Pressing Space on Retry did not trigger a new request"
    assert preview.loading


def test_tab_passes_the_preview_in_three_stops_or_fewer(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    held: list[Any] = []
    original = s.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    s.client.request = request
    create(qapp, win, "tab_stops_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    # Populate week and day with homework
    s.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": "2026-11-08T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    s.add_block(
        {
            "id": "hw_block",
            "title": "Study French",
            "kind": "flexible",
            "category": "homework",
            "start": "17:00",
            "duration_min": 45,
            "days": [1],
        }
    )
    s.save()
    wait_until(qapp, lambda: not s.busy and s.pending_save is None)

    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    quick = win._material_page._quick

    root = win._material_page.root
    stage = _named(root, "previewStage")[0]

    def is_descendant(item: Any, ancestor: Any) -> bool:
        curr = item
        while curr is not None:
            if curr is ancestor:
                return True
            curr = curr.parentItem() if hasattr(curr, "parentItem") else None
        return False

    def traverse_stops() -> list[str]:
        preview_view = _named(stage, "previewView")[0]
        preview_view.forceActiveFocus()
        pump(qapp)
        seen_items: list[Any] = [preview_view]
        for _ in range(25):
            QTest.keyClick(quick, Qt.Key.Key_Tab)
            pump(qapp)
            focused = quick.quickWindow().activeFocusItem()
            if focused is not None and is_descendant(focused, stage) and focused not in seen_items:
                seen_items.append(focused)
        return [item.objectName() for item in seen_items]

    # Test Week and Day previews
    for view in ("week", "day"):
        panel.setPreviewView(view)
        QTest.qWait(180)
        stops = traverse_stops()
        assert len(stops) <= 3, f"Expected <= 3 stops for {view}, got {len(stops)}: {stops}"
        assert "previewView" in stops, f"previewView missing from {view} stops: {stops}"
        assert "previewFit" in stops, f"previewFit missing from {view} stops: {stops}"

    # Test Month preview in success state
    panel.setPreviewView("month")
    QTest.qWait(180)
    if held:
        held[-1][3](snap("2026-11"))
        QTest.qWait(100)
    month_stops = traverse_stops()
    assert len(month_stops) <= 3, f"Expected <= 3 stops for month, got {len(month_stops)}: {month_stops}"
    assert "previewView" in month_stops
    assert "previewFit" in month_stops

    # Test Month preview in error state: Retry is one of the stops
    preview = panel._preview._passive_month
    preview._preview_snapshot = None
    preview._snapshot_month = None
    held.clear()
    preview.retry()
    QTest.qWait(100)
    assert len(held) >= 1
    held[-1][4](ApiError(503, "Failed to load month"))
    QTest.qWait(100)
    assert preview.loadError != ""

    err_stops = traverse_stops()
    assert len(err_stops) <= 3, f"Expected <= 3 stops in error state, got {len(err_stops)}: {err_stops}"
    assert "previewView" in err_stops
    assert "previewFit" in err_stops
    assert "monthPreviewRetry" in err_stops
