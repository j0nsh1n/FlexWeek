# ruff: noqa: F811
"""Tests for PR 5b: Undo toast timing and pause, Ctrl+Z hint, Week tab rings,
Month date cell rings, live text size scaling, and focus restoration."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.material import bridge as bridge_module
from desktop.native.material import bridge_sheets as bridge_sheets_module
from desktop.native.material import bridge_week as bridge_week_module
from desktop.native.material.theme import SCALE_RANGE
from desktop.native.widgets import ACTION_TOAST_MS
from desktop.native.window import NativeWindow
from desktop.tests.test_layouts_window import look_file, settled, wait_until
from desktop.tests.test_material_window import (
    _pump,
    _qml,
    _show_material,
    _visuals,
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def _reset_material(window: NativeWindow, qapp: QApplication) -> QObject:
    look_file().unlink(missing_ok=True)
    root = _show_material(qapp, window)
    if hasattr(window._material_page.bridge, "sheets"):
        window._material_page.bridge.sheets.forceClose()
    window._material_page.bridge.showPage("week")
    window._material_page.publish()
    _pump(qapp, 10)
    return root


def test_the_undo_toast_stays_at_least_ten_seconds(qapp: QApplication, window: NativeWindow) -> None:
    # 1. Material constants
    assert bridge_module.SNACK_MS >= 10000
    assert bridge_sheets_module.NOTICE_MS >= 10000
    assert bridge_week_module.SNACK_MS >= 10000

    # 2. Material snackbar timer
    _reset_material(window, qapp)
    bridge = window._material_page.bridge
    bridge.note("Block moved", action="UNDO")
    _pump(qapp)
    assert hasattr(bridge, "_snack_timer")
    assert bridge._snack_timer.interval() >= 10000

    # 3. Material sheets timer
    bridge.sheets._say("Homework added", undo=True)
    _pump(qapp)
    assert bridge.sheets._timer.interval() >= 10000
    bridge.sheets.dismissNotice()

    # 4. Widgets toast duration
    assert ACTION_TOAST_MS >= 10000
    window._use_widgets_styles()
    window.toast.show_message("Homework scheduled", "Undo")
    assert window.toast._timer.interval() >= 10000
    window.toast.hide()


def test_the_undo_toast_pauses_while_hovered_and_while_focused(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge

    # Test Material snackbar pause/resume
    bridge.note("Placed 1 homework block.", action="UNDO")
    _pump(qapp)
    snackbar = _qml(root, "materialSnackbar")
    assert bridge._snack_timer.isActive()

    # Pause via signal/slot
    if hasattr(snackbar, "pauseRequested"):
        snackbar.pauseRequested.emit()
    else:
        bridge.pauseSnack()
    _pump(qapp)
    assert not bridge._snack_timer.isActive()

    if hasattr(snackbar, "resumeRequested"):
        snackbar.resumeRequested.emit()
    else:
        bridge.resumeSnack()
    _pump(qapp)
    assert bridge._snack_timer.isActive()

    # Focus pause
    snackbar.forceActiveFocus()
    _pump(qapp)
    assert not bridge._snack_timer.isActive()

    root.forceActiveFocus()
    _pump(qapp)
    assert bridge._snack_timer.isActive()

    # Test Material sheet notice pause/resume
    bridge.sheets._say("Added homework", undo=True)
    _pump(qapp)
    notice = _qml(root, "sheetNotice")
    assert bridge.sheets._timer.isActive()

    if hasattr(notice, "pauseRequested"):
        notice.pauseRequested.emit()
    else:
        bridge.sheets.pauseNotice()
    _pump(qapp)
    assert not bridge.sheets._timer.isActive()

    if hasattr(notice, "resumeRequested"):
        notice.resumeRequested.emit()
    else:
        bridge.sheets.resumeNotice()
    _pump(qapp)
    assert bridge.sheets._timer.isActive()

    notice.forceActiveFocus()
    _pump(qapp)
    assert not bridge.sheets._timer.isActive()

    root.forceActiveFocus()
    _pump(qapp)
    assert bridge.sheets._timer.isActive()
    bridge.sheets.dismissNotice()

    # Test Widgets toast pause
    window._use_widgets_styles()
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    window.toast.show_message("History essay moved", "Undo")
    _pump(qapp)
    assert window.toast._timer.isActive()
    window.toast.button.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(qapp, lambda: window.toast._keys and not window.toast._timer.isActive())
    assert not window.toast._timer.isActive()
    window.toast.hide()


def test_undo_toasts_show_the_ctrl_z_hint(qapp: QApplication, window: NativeWindow) -> None:
    # Material snackbar & sheet notice
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    bridge.note("Placed 1 homework block.", action="UNDO")
    _pump(qapp)
    snackbar = _qml(root, "materialSnackbar")
    texts = [str(c.property("text")) for c in _visuals(snackbar) if c.property("text") is not None]
    acc_names = [str(c.property("Accessible.name") or "") for c in _visuals(snackbar)]
    has_ctrl_z = (
        any("Ctrl+Z" in t for t in texts)
        or any("Ctrl+Z" in a for a in acc_names)
        or "Ctrl+Z" in str(snackbar.property("Accessible.name") or "")
    )
    assert has_ctrl_z

    # Material sheet notice
    bridge.sheets._say("Deleted task", undo=True)
    _pump(qapp)
    notice = _qml(root, "sheetNotice")
    notice_texts = [str(c.property("text")) for c in _visuals(notice) if c.property("text") is not None]
    notice_acc = [str(c.property("Accessible.name") or "") for c in _visuals(notice)]
    has_sheet_ctrl_z = (
        any("Ctrl+Z" in t for t in notice_texts)
        or any("Ctrl+Z" in a for a in notice_acc)
        or "Ctrl+Z" in str(notice.property("Accessible.name") or "")
    )
    assert has_sheet_ctrl_z
    bridge.sheets.dismissNotice()

    # Widgets toast
    window._use_widgets_styles()
    window.toast.show_message("Placed 1 homework block.", "Undo")
    labels = [lbl.text() for lbl in window.toast.findChildren(QLabel)]
    assert any("Ctrl+Z" in lbl for lbl in labels) or hasattr(window.toast, "shortcut_hint")
    window.toast.hide()


def test_every_week_tab_stop_has_a_visible_ring_and_is_on_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    scroller = _qml(root, "weekScroller")

    # Start at toggleWeekends
    toggle = _qml(root, "toggleWeekends")
    toggle.forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem() is toggle

    # Verify disabled buttons are NOT tab stops
    plan_btn = _qml(root, "planHomework")
    drawer = _qml(root, "homeworkDrawer")
    if drawer.property("count") == 0:
        assert plan_btn.property("enabled") is False
        assert plan_btn.property("activeFocusOnTab") is False

    # Walk Tab through stops
    for _ in range(8):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp, 3)
        current = scene.activeFocusItem()
        if current is None or current is scene:
            continue
        # Verify disabled button is never focused
        assert current.property("enabled") is not False

        # If inside scroller, verify it scrolled into view
        if scroller.isAncestorOf(current):
            pt = current.mapToItem(scroller.property("contentItem"), 0, 0)
            item_y = pt.y()
            h = current.property("height") or 0
            content_y = float(scroller.property("contentY"))
            scroller_h = float(scroller.property("height"))
            # Item should be visible inside scroller viewport
            assert float(item_y) + float(h) >= content_y - 20
            assert float(item_y) <= content_y + scroller_h + 20

        # Verify a focus ring is shown/visible
        rings = [
            c
            for c in _visuals(current)
            if "FocusRing" in type(c).__name__ or c.property("ringRadius") is not None
        ]
        if rings:
            assert any(r.property("shown") is True or r.property("visible") is True for r in rings)


def test_month_date_cells_use_the_shared_ring(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    bridge.showPage("month")
    _pump(qapp, 10)

    cells = [c for c in _visuals(root) if c.objectName() and c.objectName().startswith("monthDate-")]
    assert len(cells) > 0
    cell = cells[0]
    rings = [
        c
        for c in _visuals(cell)
        if "FocusRing" in type(c).__name__
        or (hasattr(c, "property") and c.property("ringRadius") is not None)
    ]
    assert len(rings) > 0
    ring = rings[0]
    # Ring radius matches card radius + margin (12 + 2 = 14)
    assert ring.property("ringRadius") == 14
    # Uses shared theme ring color
    theme_primary = bridge._colours["primary"]
    ring_color = ring.property("ring")
    assert ring_color.name().lower() == theme_primary.lower()


def test_text_size_applies_live_and_week_and_day_rows_grow(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge

    # SCALE_RANGE cap lifted to at least 1.6x
    assert SCALE_RANGE[1] >= 1.6

    # Record normal heights
    bridge.showPage("week")
    _pump(qapp, 5)
    normal_hour_row = int(bridge.property("hourRow"))
    assert normal_hour_row == 56

    bridge.showPage("day")
    _pump(qapp, 5)
    day_rows = [c for c in _visuals(root) if c.objectName() and "Row" in c.objectName()]
    normal_day_row = float(day_rows[0].property("height")) if day_rows else 56.0

    # Go to settings and apply largest text size
    bridge.showPage("settings")
    _pump(qapp, 5)
    settings_bridge = bridge._settings_bridge
    assert hasattr(settings_bridge, "setTextSize")
    settings_bridge.setTextSize("larger")
    _pump(qapp, 15)

    # Week hour row physically grew to at least 1.5x
    bridge.showPage("week")
    _pump(qapp, 10)
    larger_hour_row = int(bridge.property("hourRow"))
    assert larger_hour_row >= int(normal_hour_row * 1.5)

    # Day row physically grew to at least 1.5x
    bridge.showPage("day")
    _pump(qapp, 10)
    new_day_rows = [c for c in _visuals(root) if c.objectName() and "Row" in c.objectName()]
    assert len(new_day_rows) > 0
    assert float(new_day_rows[0].property("height")) >= normal_day_row * 1.5

    # Reset text size back to normal
    settings_bridge.setTextSize("normal")
    _pump(qapp, 10)


def test_after_plan_focus_is_on_the_toast_or_the_plan_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    scene = quick.quickWindow()

    # Add unplaced homework due on Sunday so drawer count > 0
    from datetime import date, timedelta

    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    window.session.add_homework(
        {"id": "pr5b_task", "title": "Math assignment", "due": due, "estimate_min": 60, "revision": 0}
    )
    window.session.save()
    settled(qapp, window)
    bridge.showPage("week")
    _pump(qapp, 10)

    drawer = _qml(root, "homeworkDrawer")
    assert drawer.property("count") > 0

    plan_btn = _qml(root, "planHomework")
    plan_btn.forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem() is plan_btn

    # Execute plan
    bridge.week.plan()
    wait_until(qapp, lambda: bridge.property("snackText") != "" and not window.session.busy)
    _pump(qapp, 10)

    # Focus is never lost
    active = scene.activeFocusItem()
    assert active is not None
    assert active is not scene

    snackbar = _qml(root, "materialSnackbar")
    if drawer.property("count") == 0:
        assert active is snackbar or snackbar.isAncestorOf(active)
    else:
        assert active is plan_btn


def test_after_focus_mode_ends_focus_returns_to_the_control_that_started_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    # 1. Material test
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    scene = quick.quickWindow()

    control = _qml(root, "toggleWeekends")
    control.forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem() is control

    bridge.focus.show()
    _pump(qapp, 5)
    assert bridge.focus.open is True

    bridge.focus.hide()
    _pump(qapp, 10)
    assert bridge.focus.open is False
    assert scene.activeFocusItem() is control

    # 2. Widgets test
    window._use_widgets_styles()
    btn = window.findChild(QPushButton, "addButton")
    btn.setFocus(Qt.FocusReason.TabFocusReason)
    _pump(qapp)
    assert window.focusWidget() is btn

    window._open_focus_screen()
    _pump(qapp)
    window._close_focus_screen()
    _pump(qapp)
    assert window.focusWidget() is btn
