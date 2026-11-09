"""Tab through the Material week: every stop takes the keyboard, shows its ring, never falls out of the
window, scrolls into view if it was below the first screenful, and the cycle wraps. What the ring looks
like is a picture (desktop/tests/pictures/_month_g14.py has the shared ring on Month's dates)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, qml, visuals
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-material-tab-stops"])


def rings_of(item: object) -> list:
    return [
        child
        for child in visuals(item)
        if "FocusRing" in type(child).__name__
        or (hasattr(child, "property") and child.property("ringRadius") is not None)
    ]


def test_every_week_tab_stop_has_a_visible_ring_and_is_on_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = fresh_material(qapp, window)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    scroller = qml(root, "weekScroller")
    bridge = window._material_page.bridge

    # A homework block out of view first (late evening, 21:00), so Tab must scroll to it
    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    window.session.add_homework(
        {"id": "late_hw", "title": "Late essay", "due": due, "estimate_min": 60, "revision": 0}
    )
    window.session.add_block(
        {
            "id": "late_block",
            "title": "Late essay",
            "kind": "flexible",
            "start": "21:00",
            "duration_min": 60,
            "days": [2],
            "assignment_id": "late_hw",
        }
    )
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    bridge.refresh()
    pump(qapp, 10)

    # Start from the first Week control
    first = qml(root, "toggleWeekends")
    first.forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem() is first

    # A disabled button is not a tab stop
    plan_btn = qml(root, "planHomework")
    drawer = qml(root, "homeworkDrawer")
    if drawer.property("count") == 0:
        assert plan_btn.property("enabled") is False
        assert plan_btn.property("activeFocusOnTab") is False

    visited = []
    prev_item = first
    wrapped = False

    for step in range(60):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        pump(qapp, 5)
        current = scene.activeFocusItem()

        # At every press there is a focus item, and it is not the window itself
        assert current is not None, f"focus was None at step {step}"
        assert current is not scene, f"focus fell back to window at step {step}"
        assert current is not prev_item, f"focus did not advance at step {step}: stayed on {current}"
        if current is first:
            wrapped = True
            break
        prev_item = current
        visited.append(current)

        rings = rings_of(current)
        if not rings and current.property("ringRadius") is not None:
            rings = [current]
        assert len(rings) > 0, f"no ring found on focused item {current} ({current.objectName()})"
        ring_active = any(
            r.property("shown") is True
            or (r.property("visible") is True and float(r.property("opacity")) > 0)
            for r in rings
        )
        assert ring_active, f"ring not shown on {current} ({current.objectName()})"

        # Tab reveals the stop: the whole item is inside the Week scroller's viewport, or inside the
        # window when it is outside the scroller.
        height = float(current.property("height") or 0)
        if scroller.isAncestorOf(current):
            top = float(current.mapToItem(scroller.property("contentItem"), 0, 0).y())
            content_y = float(scroller.property("contentY"))
            bottom_edge = content_y + float(scroller.property("height")) + 2
            shown = top >= content_y - 2 and top + height <= bottom_edge
            assert shown, f"item {current.objectName()} at {top} is outside the viewport at {content_y}"
        else:
            top = float(current.mapToItem(root, 0, 0).y())
            assert top >= -2 and top + height <= float(root.property("height")) + 2, current.objectName()

    assert wrapped is True, "Tab cycle did not wrap back to the first control"

    def late(item) -> bool:
        while item is not None:
            if item.property("title") == "Late essay":
                return True
            item = item.parentItem()
        return False

    names = [item.objectName() for item in visited]
    # The late block sits below the first screenful, so reaching it whole proves the reveal.
    assert any(item.objectName() == "weekBlock" and late(item) for item in visited), names
    assert any(item.objectName() == "weekBlockFinish" and late(item) for item in visited), names
    for expected in ("weekPrevious", "weekToday", "weekNext", "navWeek", "materialFab"):
        assert expected in names, (expected, names)
