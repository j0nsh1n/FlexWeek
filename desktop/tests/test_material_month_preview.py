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
)
from desktop.tests.test_material_month_lifecycle import snap, totals
from desktop.tests.test_material_static_audit import _bridge, _named, _panel
from desktop.tests.test_material_window import _visuals

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


def test_after_undo_the_preview_shows_the_new_counts_without_reopening(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    # Preview active, initial November snapshot
    held.calls[0][3](snap("2026-11", "Initial homework"))
    assert totals(preview) == (75, 75)
    assert len(held.calls) == 1

    # Simulate undo occurring on session:
    # undo() calls save() which clears _month_cache, increments _month_gen, and emits week_changed
    session._month_cache.clear()
    session._month_gen = getattr(session, "_month_gen", 0) + 1
    session.week_changed.emit()

    # The preview should ask again without needing to close or reopen
    assert len(held.calls) == 2, "Preview did not re-fetch after undo"
    # Settle second request with updated counts
    held.calls[1][3](
        {
            "month": "2026-11",
            "days": [
                {
                    "date": "2026-11-23",
                    "in_month": True,
                    "blocks": [
                        {
                            "id": "b1",
                            "title": "Undone HW",
                            "category": "homework",
                            "start": "17:00",
                            "duration_min": 30,
                            "completed": False,
                        },
                        {
                            "id": "b2",
                            "title": "Done HW",
                            "category": "homework",
                            "start": "18:00",
                            "duration_min": 45,
                            "completed": True,
                        },
                    ],
                }
            ],
        }
    )
    assert totals(preview) == (75, 45)


def test_after_a_save_the_preview_asks_again(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap("2026-11"))
    assert preview._preview_snapshot is not None
    assert not preview.loading
    assert len(held.calls) == 1

    # Simulate a save on session
    session._month_cache.clear()
    session._month_gen = getattr(session, "_month_gen", 0) + 1
    session.week_changed.emit()

    # Preview snapshot cleared, asks again, loading is True
    assert preview._preview_snapshot is None
    assert len(held.calls) == 2, "Preview did not ask again after save"
    assert preview.loading


def test_a_late_reply_after_a_save_does_not_land_in_the_cache(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    old_call = held.calls[0]
    # Request 0 is in flight for November

    # Save happens while request 0 is in flight
    session._month_cache.clear()
    session._month_gen = getattr(session, "_month_gen", 0) + 1
    session.week_changed.emit()

    # New request is dispatched (call 1)
    assert len(held.calls) == 2
    new_call = held.calls[1]

    # Stale reply from old request 0 arrives
    stale_payload = snap("2026-11", "Stale homework from old generation")
    old_call[3](stale_payload)

    # Stale reply must NOT land in cache, must NOT set _preview_snapshot,
    # and must NOT clear loading for newer request
    assert ("A", "2026-11") not in session._month_cache
    assert preview._preview_snapshot is None
    assert preview.loading, "Stale reply cleared loading for newer request"

    # New request reply arrives
    fresh_payload = snap("2026-11", "Fresh homework from new generation")
    new_call[3](fresh_payload)
    assert preview._preview_snapshot == fresh_payload
    assert not preview.loading


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
    call[3](snap())
    assert not preview.loading

    # 2. ok: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = {"id": "OTHER"}
    call[3](snap())
    assert not preview.loading

    # 3. ok: invalid payload or mismatched month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    call[3]({"month": "2026-12", "days": []})  # Mismatched month for November request
    assert not preview.loading

    # 4. err: current_session is None
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    live.session = None
    call[4](ApiError(500, "error"))
    assert not preview.loading

    # 5. err: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = None
    call[4](ApiError(500, "error"))
    assert not preview.loading

    # 6. err: self._target_month() != target_month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.selected_month = "2026-12"
    call[4](ApiError(500, "error"))
    assert not preview.loading


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

    retry_btn.forceActiveFocus()
    pump(qapp)
    assert retry_btn.property("activeFocus") is True

    initial_requests = len(held)
    quick = win._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp)
    QTest.qWait(100)

    assert len(held) > initial_requests, "Pressing Space on Retry did not trigger a new request"
    assert preview.loading


def test_tab_passes_the_preview_in_three_stops_or_fewer(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    create(qapp, win, "tab_stops_user")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    _bridge(win).showPage("settings")
    panel = _panel(win)
    panel.openAdvanced()
    panel.setPreviewView("month")
    QTest.qWait(180)

    root = win._material_page.root
    preview_stage = _named(root, "previewStage")[0]

    def find_tab_stops(item: Any) -> list[Any]:
        stops = []
        for child in item.childItems():
            if child.property("activeFocusOnTab") and child.property("visible"):
                stops.append(child)
            stops.extend(find_tab_stops(child))
        return stops

    stops = find_tab_stops(preview_stage)
    assert len(stops) <= 3, f"Expected 3 stops or fewer, got {len(stops)}: {[s.objectName() for s in stops]}"

    month_view = _named(preview_stage, "materialMonth")[0]
    cells = [c for c in _visuals(month_view) if str(c.objectName()).startswith("monthDate-")]
    assert all(not c.property("activeFocusOnTab") for c in cells)
    prev_btn = _named(month_view, "monthPrev")[0]
    next_btn = _named(month_view, "monthNext")[0]
    assert not prev_btn.property("visible")
    assert not next_btn.property("visible")
    assert not prev_btn.property("activeFocusOnTab")
    assert not next_btn.property("activeFocusOnTab")
