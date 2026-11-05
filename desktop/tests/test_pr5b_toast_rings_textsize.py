# ruff: noqa: F811
"""Tests for PR 5b: Undo toast timing and pause, Ctrl+Z hint, Week tab rings,
Month date cell rings, live text size scaling, and focus restoration."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.material import bridge as bridge_module
from desktop.native.material import bridge_sheets as bridge_sheets_module
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
        window._material_page.bridge.sheets.dismissNotice()
    window._material_page.bridge.note("")
    window._material_page.bridge.showPage("week")
    window._material_page.publish()
    _pump(qapp, 10)
    return root


def test_the_undo_toast_stays_at_least_ten_seconds(qapp: QApplication, window: NativeWindow) -> None:
    # 1. Material constants
    assert bridge_module.SNACK_MS >= 10000
    assert bridge_sheets_module.NOTICE_MS >= 10000

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
    # Material snackbar
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    bridge.note("Placed 1 homework block.", action="UNDO")
    _pump(qapp)
    snackbar = _qml(root, "materialSnackbar")
    assert snackbar.property("visible") is True
    hint = _qml(snackbar, "shortcutHint")
    assert hint is not None
    assert hint.property("visible") is True
    assert float(hint.property("opacity")) > 0
    assert "Ctrl+Z" in str(hint.property("text"))

    # Material sheet notice
    bridge.sheets._say("Deleted task", undo=True)
    _pump(qapp)
    notice = _qml(root, "sheetNotice")
    assert notice.property("visible") is True
    sheet_hint = _qml(notice, "shortcutHint")
    assert sheet_hint is not None
    assert sheet_hint.property("visible") is True
    assert float(sheet_hint.property("opacity")) > 0
    assert "Ctrl+Z" in str(sheet_hint.property("text"))
    bridge.sheets.dismissNotice()

    # Widgets toast
    window._surface = "widgets"
    window._use_widgets_styles()
    window._show_surface()
    window.toast.show_message("Placed 1 homework block.", "Undo")
    _pump(qapp)
    widget_hint = getattr(window.toast, "shortcut_hint", None)
    assert widget_hint is not None
    assert widget_hint.isVisible() is True
    assert "Ctrl+Z" in widget_hint.text()
    window.toast.hide()


def test_every_week_tab_stop_has_a_visible_ring_and_is_on_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    scroller = _qml(root, "weekScroller")
    bridge = window._material_page.bridge

    # Put a homework block out of view first (late evening, 21:00) so Tab must scroll to it
    from datetime import date, timedelta

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
    settled(qapp, window)
    bridge.refresh()
    _pump(qapp, 10)

    # Start from the first Week control
    first = _qml(root, "toggleWeekends")
    first.forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem() is first

    # Verify disabled buttons are NOT tab stops
    plan_btn = _qml(root, "planHomework")
    drawer = _qml(root, "homeworkDrawer")
    if drawer.property("count") == 0:
        assert plan_btn.property("enabled") is False
        assert plan_btn.property("activeFocusOnTab") is False

    visited = []
    prev_item = first
    wrapped = False

    # Walk Tab stops
    for step in range(60):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp, 5)
        current = scene.activeFocusItem()

        # At EVERY press require a non-null focus item that is not the window
        assert current is not None, f"focus was None at step {step}"
        assert current is not scene, f"focus fell back to window at step {step}"

        # A changed objectName or item from the press before (until the cycle wraps)
        assert current is not prev_item, f"focus did not advance at step {step}: stayed on {current}"
        if current is first:
            wrapped = True
            break
        prev_item = current
        visited.append(current)

        # A ring that is shown
        rings = [
            c
            for c in _visuals(current)
            if "FocusRing" in type(c).__name__
            or (hasattr(c, "property") and c.property("ringRadius") is not None)
        ]
        if not rings and hasattr(current, "property") and current.property("ringRadius") is not None:
            rings = [current]
        assert len(rings) > 0, f"no ring found on focused item {current} ({current.objectName()})"
        ring_active = any(
            r.property("shown") is True
            or (r.property("visible") is True and float(r.property("opacity")) > 0)
            for r in rings
        )
        assert ring_active, f"ring not shown on {current} ({current.objectName()})"

        # Focused item whole rectangle inside Week scroller viewport (or inside window if outside scroller)
        if scroller.isAncestorOf(current):
            pt = current.mapToItem(scroller.property("contentItem"), 0, 0)
            item_y = float(pt.y())
            h = float(current.property("height") or 0)
            content_y = float(scroller.property("contentY"))
            scroller_h = float(scroller.property("height"))
            name = current.objectName()
            assert item_y >= content_y - 2, f"item {name} top {item_y} above scroller viewport {content_y}"
            assert item_y + h <= content_y + scroller_h + 2, (
                f"item {name} bottom {item_y + h} below viewport {content_y + scroller_h}"
            )
        else:
            pt = current.mapToItem(root, 0, 0)
            item_y = float(pt.y())
            h = float(current.property("height") or 0)
            root_h = float(root.property("height"))
            assert item_y >= -2, f"item {current.objectName()} top {item_y} above window"
            assert item_y + h <= root_h + 2, f"item {current.objectName()} bottom {item_y + h} below window"

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


def test_undo_toast_expiry_solely_owned_by_shell_and_held_toast_survives(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge

    from datetime import date, timedelta

    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    window.session.add_homework(
        {"id": "hw_done_task", "title": "History essay", "due": due, "estimate_min": 60, "revision": 0}
    )
    window.session.save()
    settled(qapp, window)
    bridge.showPage("week")
    _pump(qapp, 10)

    # Mark homework finished on the real Week screen
    bridge.week.toggleDone("hw_done_task")
    wait_until(qapp, lambda: not window.session.busy and bridge.property("snackText").startswith("Finished"))
    _pump(qapp, 5)

    # Hold the toast with keyboard focus
    snackbar = _qml(root, "materialSnackbar")
    snackbar.forceActiveFocus()
    _pump(qapp, 5)

    # Fire every expiry timer the bridges own
    all_timers = bridge.findChildren(QTimer) + bridge.week.findChildren(QTimer)
    for timer in all_timers:
        if timer.isActive():
            timer.timeout.emit()
    _pump(qapp, 5)

    # The toast text must still be there
    assert bridge.property("snackText") != ""
    assert bridge.property("snackText").startswith("Finished")

    # Also the _on_status path (a plan answer that places nothing)
    import time

    bridge.week._said_plan = time.monotonic()
    bridge.week._on_status("Nothing to place")
    _pump(qapp, 5)
    assert bridge.property("snackText") == "Nothing to place"

    snackbar.forceActiveFocus()
    _pump(qapp, 5)
    all_timers = bridge.findChildren(QTimer) + bridge.week.findChildren(QTimer)
    for timer in all_timers:
        if timer.isActive():
            timer.timeout.emit()
    _pump(qapp, 5)
    assert bridge.property("snackText") == "Nothing to place"


def test_new_notice_starts_with_full_duration_after_shortened_interval(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset_material(window, qapp)
    bridge = window._material_page.bridge

    # Sheet notice
    bridge.sheets._say("First notice", undo=True)
    _pump(qapp)
    # Simulate a notice resumed late with shortened interval
    bridge.sheets._timer.start(2400)
    bridge.sheets.pauseNotice()
    bridge.sheets.resumeNotice()
    assert bridge.sheets._timer.interval() <= 3000

    # Show a second notice - must start with full NOTICE_MS (10000)
    bridge.sheets._say("Second notice", undo=True)
    _pump(qapp)
    assert bridge.sheets._timer.interval() == bridge_sheets_module.NOTICE_MS

    # Shell snackbar
    bridge.note("First snack", action="UNDO")
    _pump(qapp)
    bridge._snack_timer.start(2400)
    bridge.pauseSnack()
    bridge.resumeSnack()
    assert bridge._snack_timer.interval() <= 3000

    bridge.note("Second snack", action="UNDO")
    _pump(qapp)
    assert bridge._snack_timer.interval() == bridge_module.SNACK_MS


def test_replacing_held_toast_keeps_timer_paused_until_resumed(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge

    # Shell snackbar: focus it
    bridge.note("First snack", action="UNDO")
    _pump(qapp)
    snackbar = _qml(root, "materialSnackbar")
    snackbar.forceActiveFocus()
    _pump(qapp)
    assert not bridge._snack_timer.isActive()

    # Replace while held: timer must NOT be active
    bridge.note("Second snack", action="UNDO")
    _pump(qapp)
    assert not bridge._snack_timer.isActive()

    # Move focus away: timer resumes with full time
    root.forceActiveFocus()
    _pump(qapp)
    assert bridge._snack_timer.isActive()
    assert bridge._snack_timer.remainingTime() > 8000

    # Sheet notice: focus it
    bridge.sheets._say("First sheet notice", undo=True)
    _pump(qapp)
    notice = _qml(root, "sheetNotice")
    notice.forceActiveFocus()
    _pump(qapp)
    assert not bridge.sheets._timer.isActive()

    # Replace while held: timer must NOT be active
    bridge.sheets._say("Second sheet notice", undo=True)
    _pump(qapp)
    assert not bridge.sheets._timer.isActive()

    # Move focus away: timer resumes with full time
    root.forceActiveFocus()
    _pump(qapp)
    assert bridge.sheets._timer.isActive()
    assert bridge.sheets._timer.remainingTime() > 8000
    bridge.sheets.dismissNotice()


def test_focus_mode_return_when_origin_is_deleted_falls_back_without_error(
    qapp: QApplication, window: NativeWindow
) -> None:
    from PySide6.QtCore import QEvent

    # 1. Material test
    root = _reset_material(window, qapp)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    scene = quick.quickWindow()

    from PySide6.QtQuick import QQuickItem

    temp_item = QQuickItem(root)
    temp_item.setObjectName("tempFocusTarget")
    temp_item.setEnabled(True)
    temp_item.setVisible(True)
    temp_item.forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem() is temp_item

    bridge.focus.show()
    _pump(qapp, 5)
    assert bridge.focus.open is True

    # Delete origin while Focus is open
    temp_item.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _pump(qapp, 5)

    # Close Focus: must not raise exception
    bridge.focus.hide()
    _pump(qapp, 10)
    assert bridge.focus.open is False

    # 2. Widgets test
    window._surface = "widgets"
    window._show_surface()
    temp_btn = QPushButton("Temp Button", window)
    temp_btn.show()
    temp_btn.setFocus(Qt.FocusReason.TabFocusReason)
    _pump(qapp)
    assert window.focusWidget() is temp_btn

    window._open_focus_screen()
    _pump(qapp)
    temp_btn.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _pump(qapp, 5)

    window._close_focus_screen()
    _pump(qapp, 5)
    hours = window._week_surfaces()[0]
    assert window.focusWidget() is hours


def test_text_size_preserved_when_preset_changes_or_saved_look_applied(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset_material(window, qapp)
    bridge = window._material_page.bridge
    settings_bridge = bridge._settings_bridge

    bridge.showPage("settings")
    _pump(qapp, 5)
    settings_bridge.setTextSize("larger")
    _pump(qapp, 5)
    assert settings_bridge.state["textSize"] == "larger"

    # Change preset and discard advanced overrides
    other_preset = "Forest" if settings_bridge.state["preset"] != "Forest" else "Rose"
    settings_bridge.setPreset(other_preset)
    _pump(qapp, 5)
    assert settings_bridge.property("promptOpen") is True
    settings_bridge.answerPreset("discard")
    _pump(qapp, 10)

    # Text size is still larger and Week hour row is still the larger height
    assert settings_bridge.state["textSize"] == "larger"
    bridge.showPage("week")
    _pump(qapp, 10)
    assert int(bridge.property("hourRow")) >= 80

    # Also test saved look: save a look (with standard scale 1.0)
    bridge.showPage("settings")
    _pump(qapp, 5)
    settings_bridge.setTextSize("normal")
    _pump(qapp, 5)
    settings_bridge.saveAs("NormalLook")
    _pump(qapp, 5)

    # Set text size to larger
    settings_bridge.setTextSize("larger")
    _pump(qapp, 5)
    assert settings_bridge.state["textSize"] == "larger"

    # Apply saved look (which had normal scale in its advanced dict)
    settings_bridge.useSaved("NormalLook")
    _pump(qapp, 10)
    # The student text size setting must be kept!
    assert settings_bridge.state["textSize"] == "larger"
    bridge.showPage("week")
    _pump(qapp, 10)
    assert int(bridge.property("hourRow")) >= 80

    # Reset text size back to normal
    settings_bridge.setTextSize("normal")
    _pump(qapp, 5)


def test_a_notice_shown_again_under_a_still_pointer_waits(qapp: QApplication, window: NativeWindow) -> None:
    """Hover a notice, dismiss it, show the next without moving the pointer: it must not count down."""
    from PySide6.QtCore import QPoint, QPointF

    root = _reset_material(window, qapp)
    quick = window._material_page._quick
    sheets = window._material_page.bridge.sheets
    sheets._say("Hover old", undo=True)
    _pump(qapp, 10)
    notice = _qml(root, "sheetNotice")
    centre = notice.mapToScene(QPointF(notice.property("width") / 2, notice.property("height") / 2))
    QTest.mouseMove(quick, QPoint(int(centre.x()), int(centre.y())))
    _pump(qapp, 10)
    assert notice.property("pointerHovered") is True
    assert not sheets._timer.isActive()
    sheets.dismissNotice()
    _pump(qapp, 10)
    sheets._say("New without moving the pointer", undo=True)
    _pump(qapp, 10)
    assert notice.property("visible") is True
    assert not sheets._timer.isActive(), "a hovered notice is counting down"
    QTest.mouseMove(quick, QPoint(2, 2))
    _pump(qapp, 10)
    assert sheets._timer.isActive()
    assert sheets._timer.remainingTime() > bridge_sheets_module.NOTICE_MS - 1000
    sheets.dismissNotice()
