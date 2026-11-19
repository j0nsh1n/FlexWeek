# ruff: noqa: F811
"""The month preview in Settings > Advanced while it loads, when it fails, and how the keyboard and the
pointer reach its Retry button. The window is a light window; the test holds the preview's month
requests and answers or fails them itself."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.client import ApiError  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.material_support import named, pump, show_material  # noqa: E402
from desktop.tests.month.support_material_month import (  # noqa: E402
    bridge,
    hold_month_requests,
    idle,
    open_month_preview,
    panel,
    preview_calls,
    snap,
)
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-preview-loading"])


def test_no_month_is_asked_for_the_preview_before_settings_is_opened(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    asked: list[str] = []
    original = session.client.request

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            asked.append(getattr(ok, "__qualname__", ""))
        return original(method, path, payload, ok, err)

    session.client.request = request
    show_material(qapp, window)
    wait_until(qapp, lambda: idle(window))

    # The live planner is on the week, with no month history.
    assert session.planner_view == "week" and session.selected_month is None and session.month_data is None
    assert [name for name in asked if "PassiveMonthBridge" in name] == []






def _fail_the_first_load(
    qapp: QApplication, window: NativeWindow, message: str
) -> tuple[Any, Any, list[tuple[Any, ...]]]:
    """Open the preview, fail its request, and wait for the Retry button. Returns the QML root, the
    month preview and the held requests."""
    held = hold_month_requests(window)
    root, _settings, preview = open_month_preview(qapp, window)
    wait_until(qapp, lambda: len(preview_calls(held)) >= 1)
    preview_calls(held)[-1][4](ApiError(503, message))
    wait_until(qapp, lambda: not preview.loading and preview.loadError == message)

    def retry_shown() -> bool:
        found = named(root, "monthPreviewRetry")
        return bool(found) and found[0].isVisible()

    wait_until(qapp, retry_shown, what="the Retry button")
    return root, preview, held






def test_tab_passes_the_preview_in_three_stops_or_fewer(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    held = hold_month_requests(window)
    root = show_material(qapp, window)
    wait_until(qapp, lambda: idle(window))

    # Homework in the week and the day, and two more waiting with no time, so the drawer holds
    # several cards.
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": "2026-11-08T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.add_block(
        {
            "id": "hw_block",
            "title": "Study French",
            "kind": "flexible",
            "category": "homework",
            "start": "17:00",
            "duration_min": 45,
            "days": [1],
            "assignment_id": "essay",
        }
    )
    for extra in ("lab", "reading"):
        session.add_homework(
            {
                "id": extra,
                "title": extra.title(),
                "due": "2026-11-08T23:59",
                "estimate_min": 30,
                "revision": 0,
            }
        )
    session.save()
    wait_until(qapp, lambda: idle(window))

    bridge(window).showPage("settings")
    settings = panel(window)
    settings.openAdvanced()
    quick = window._material_page._quick
    stage = named(root, "previewStage")[0]

    def is_descendant(item: Any, ancestor: Any) -> bool:
        current = item
        while current is not None:
            if current is ancestor:
                return True
            current = current.parentItem() if hasattr(current, "parentItem") else None
        return False

    def traverse_stops() -> list[str]:
        preview_view = named(stage, "previewView")[0]
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

    def drawn() -> bool:
        return bool(named(stage, "previewView")) and bool(named(stage, "previewFit"))

    for view in ("week", "day"):
        settings.setPreviewView(view)
        wait_until(qapp, drawn, what=f"the {view} preview")
        if view == "week":
            wait_until(
                qapp,
                lambda: bool(named(stage, "weekBlock")) and len(named(stage, "homeworkCard")) >= 2,
                what="the scheduled block and the waiting cards",
            )
        stops = traverse_stops()
        assert len(stops) <= 3, f"Expected <= 3 stops for {view}, got {len(stops)}: {stops}"
        assert "previewView" in stops, f"previewView missing from {view} stops: {stops}"
        assert "previewFit" in stops, f"previewFit missing from {view} stops: {stops}"
        if view == "week":
            assert named(stage, "weekBlock"), "the Week preview draws the scheduled homework block"
            assert len(named(stage, "homeworkCard")) >= 2, "the Week preview draws the waiting cards"
        for name in ("weekBlock", "weekBlockFinish", "homeworkCard", "planHomework"):
            assert name not in stops, f"{name} took a Tab stop in the {view} preview: {stops}"

    # The month preview with its month loaded.
    settings.setPreviewView("month")
    preview = settings._preview._passive_month
    wait_until(qapp, lambda: len(preview_calls(held)) >= 1, what="the month preview asking")
    preview_calls(held)[-1][3](snap("2026-11"))
    wait_until(qapp, lambda: not preview.loading)
    wait_until(qapp, drawn, what="the month preview")
    month_stops = traverse_stops()
    assert len(month_stops) <= 3, f"Expected <= 3 stops for month, got {len(month_stops)}: {month_stops}"
    assert "previewView" in month_stops
    assert "previewFit" in month_stops

    # The month preview after a failed load: Retry is one of the stops.
    preview._preview_snapshot = None
    preview._snapshot_month = None
    held.clear()
    preview.retry()
    wait_until(qapp, lambda: len(preview_calls(held)) >= 1)
    preview_calls(held)[-1][4](ApiError(503, "Failed to load month"))
    wait_until(qapp, lambda: preview.loadError != "")
    wait_until(qapp, lambda: bool(named(stage, "monthPreviewRetry")))

    err_stops = traverse_stops()
    assert len(err_stops) <= 3, f"Expected <= 3 stops in error state, got {len(err_stops)}: {err_stops}"
    assert "previewView" in err_stops
    assert "previewFit" in err_stops
    assert "monthPreviewRetry" in err_stops


