"""The Undo notice after a change: how long it stays, that hovering or focusing it holds it, the Ctrl+Z hint
it shows, what a shorter-lived or replaced notice does to the clock, and where the keyboard is afterwards.
Material's snackbar and sheet notice, and Widgets' toast, are held to the same rules."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QStandardPaths, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.material import bridge as bridge_module
from desktop.native.material import bridge_sheets as bridge_sheets_module
from desktop.native.widgets import ACTION_TOAST_MS
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, qml
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-undo-toast"])


def add_homework(qapp: QApplication, window: NativeWindow, key: str, title: str) -> None:
    """A homework due on Sunday that is not placed yet."""
    due = (date.fromisoformat(window.session.week_start) + timedelta(days=6)).isoformat()
    window.session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def test_the_undo_toast_stays_at_least_ten_seconds(qapp: QApplication, window: NativeWindow) -> None:
    # Material's constants
    assert bridge_module.SNACK_MS >= 10000
    assert bridge_sheets_module.NOTICE_MS >= 10000

    # Material snackbar timer
    fresh_material(qapp, window)
    bridge = window._material_page.bridge
    bridge.note("Block moved", action="UNDO")
    pump(qapp)
    assert hasattr(bridge, "_snack_timer")
    assert bridge._snack_timer.interval() >= 10000

    # Material sheet notice timer
    bridge.sheets._say("Homework added", undo=True)
    pump(qapp)
    assert bridge.sheets._timer.interval() >= 10000
    bridge.sheets.dismissNotice()

    # Widgets toast duration
    assert ACTION_TOAST_MS >= 10000
    window._use_widgets_styles()
    window.toast.show_message("Homework scheduled", "Undo")
    assert window.toast._timer.interval() >= 10000
    window.toast.hide()


def test_the_undo_toast_pauses_while_hovered_and_while_focused(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge

    # Material snackbar pause and resume
    bridge.note("Placed 1 homework block.", action="UNDO")
    pump(qapp)
    snackbar = qml(root, "materialSnackbar")
    assert bridge._snack_timer.isActive()

    if hasattr(snackbar, "pauseRequested"):
        snackbar.pauseRequested.emit()
    else:
        bridge.pauseSnack()
    pump(qapp)
    assert not bridge._snack_timer.isActive()

    if hasattr(snackbar, "resumeRequested"):
        snackbar.resumeRequested.emit()
    else:
        bridge.resumeSnack()
    pump(qapp)
    assert bridge._snack_timer.isActive()

    # Focus pauses it too
    snackbar.forceActiveFocus()
    pump(qapp)
    assert not bridge._snack_timer.isActive()

    root.forceActiveFocus()
    pump(qapp)
    assert bridge._snack_timer.isActive()

    # Material sheet notice pause and resume
    bridge.sheets._say("Added homework", undo=True)
    pump(qapp)
    notice = qml(root, "sheetNotice")
    assert bridge.sheets._timer.isActive()

    if hasattr(notice, "pauseRequested"):
        notice.pauseRequested.emit()
    else:
        bridge.sheets.pauseNotice()
    pump(qapp)
    assert not bridge.sheets._timer.isActive()

    if hasattr(notice, "resumeRequested"):
        notice.resumeRequested.emit()
    else:
        bridge.sheets.resumeNotice()
    pump(qapp)
    assert bridge.sheets._timer.isActive()

    notice.forceActiveFocus()
    pump(qapp)
    assert not bridge.sheets._timer.isActive()

    root.forceActiveFocus()
    pump(qapp)
    assert bridge.sheets._timer.isActive()
    bridge.sheets.dismissNotice()

    # Widgets toast pause
    window._use_widgets_styles()
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    window.toast.show_message("History essay moved", "Undo")
    pump(qapp)
    assert window.toast._timer.isActive()
    window.toast.button.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(qapp, lambda: window.toast._keys and not window.toast._timer.isActive())
    assert not window.toast._timer.isActive()
    window.toast.hide()


def test_undo_toasts_show_the_ctrl_z_hint(qapp: QApplication, window: NativeWindow) -> None:
    # Material snackbar
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge
    bridge.note("Placed 1 homework block.", action="UNDO")
    pump(qapp)
    snackbar = qml(root, "materialSnackbar")
    assert snackbar.property("visible") is True
    hint = qml(snackbar, "shortcutHint")
    assert hint.property("visible") is True
    assert float(hint.property("opacity")) > 0
    assert "Ctrl+Z" in str(hint.property("text"))

    # Material sheet notice
    bridge.sheets._say("Deleted task", undo=True)
    pump(qapp)
    notice = qml(root, "sheetNotice")
    assert notice.property("visible") is True
    sheet_hint = qml(notice, "shortcutHint")
    assert sheet_hint.property("visible") is True
    assert float(sheet_hint.property("opacity")) > 0
    assert "Ctrl+Z" in str(sheet_hint.property("text"))
    bridge.sheets.dismissNotice()

    # Widgets toast
    window._surface = "widgets"
    window._use_widgets_styles()
    window._show_surface()
    window.toast.show_message("Placed 1 homework block.", "Undo")
    pump(qapp)
    widget_hint = getattr(window.toast, "shortcut_hint", None)
    assert widget_hint is not None
    assert widget_hint.isVisible() is True
    assert "Ctrl+Z" in widget_hint.text()
    window.toast.hide()


def test_after_plan_focus_is_on_the_toast_or_the_plan_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge
    scene = window._material_page._quick.quickWindow()

    # Not placed yet, so the drawer's count is above zero
    add_homework(qapp, window, "plan_task", "Math assignment")
    bridge.showPage("week")
    pump(qapp, 10)

    drawer = qml(root, "homeworkDrawer")
    assert drawer.property("count") > 0

    plan_btn = qml(root, "planHomework")
    plan_btn.forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem() is plan_btn

    bridge.week.plan()
    wait_until(qapp, lambda: bridge.property("snackText") != "" and not window.session.busy)
    pump(qapp, 10)

    # Focus is never lost
    active = scene.activeFocusItem()
    assert active is not None
    assert active is not scene

    snackbar = qml(root, "materialSnackbar")
    if drawer.property("count") == 0:
        assert active is snackbar or snackbar.isAncestorOf(active)
    else:
        assert active is plan_btn


def test_undo_toast_expiry_solely_owned_by_shell_and_held_toast_survives(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge

    add_homework(qapp, window, "hw_done_task", "History essay")
    bridge.showPage("week")
    pump(qapp, 10)

    # Mark homework finished on the real Week screen
    bridge.week.toggleDone("hw_done_task")
    wait_until(qapp, lambda: not window.session.busy and bridge.property("snackText").startswith("Finished"))
    pump(qapp, 5)

    # Hold the toast with keyboard focus
    snackbar = qml(root, "materialSnackbar")
    snackbar.forceActiveFocus()
    pump(qapp, 5)

    def fire_every_expiry_timer() -> None:
        for timer in bridge.findChildren(QTimer) + bridge.week.findChildren(QTimer):
            if timer.isActive():
                timer.timeout.emit()
        pump(qapp, 5)

    fire_every_expiry_timer()
    assert bridge.property("snackText").startswith("Finished")

    # Also the _on_status path (a plan answer that places nothing)
    bridge.week._said_plan = time.monotonic()
    bridge.week._on_status("Nothing to place")
    pump(qapp, 5)
    assert bridge.property("snackText") == "Nothing to place"

    snackbar.forceActiveFocus()
    pump(qapp, 5)
    fire_every_expiry_timer()
    assert bridge.property("snackText") == "Nothing to place"


def test_new_notice_starts_with_full_duration_after_shortened_interval(
    qapp: QApplication, window: NativeWindow
) -> None:
    fresh_material(qapp, window)
    bridge = window._material_page.bridge

    # Sheet notice
    bridge.sheets._say("First notice", undo=True)
    pump(qapp)
    # A notice resumed late has a shortened interval
    bridge.sheets._timer.start(2400)
    bridge.sheets.pauseNotice()
    bridge.sheets.resumeNotice()
    assert bridge.sheets._timer.interval() <= 3000

    # The second notice starts with the full time
    bridge.sheets._say("Second notice", undo=True)
    pump(qapp)
    assert bridge.sheets._timer.interval() == bridge_sheets_module.NOTICE_MS

    # Shell snackbar
    bridge.note("First snack", action="UNDO")
    pump(qapp)
    bridge._snack_timer.start(2400)
    bridge.pauseSnack()
    bridge.resumeSnack()
    assert bridge._snack_timer.interval() <= 3000

    bridge.note("Second snack", action="UNDO")
    pump(qapp)
    assert bridge._snack_timer.interval() == bridge_module.SNACK_MS


def test_replacing_held_toast_keeps_timer_paused_until_resumed(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = fresh_material(qapp, window)
    bridge = window._material_page.bridge

    # Shell snackbar: focus it
    bridge.note("First snack", action="UNDO")
    pump(qapp)
    snackbar = qml(root, "materialSnackbar")
    snackbar.forceActiveFocus()
    pump(qapp)
    assert not bridge._snack_timer.isActive()

    # Replaced while held, the timer stays off
    bridge.note("Second snack", action="UNDO")
    pump(qapp)
    assert not bridge._snack_timer.isActive()

    # Focus moves away: the timer resumes with the full time
    root.forceActiveFocus()
    pump(qapp)
    assert bridge._snack_timer.isActive()
    assert bridge._snack_timer.remainingTime() > 8000

    # Sheet notice: focus it
    bridge.sheets._say("First sheet notice", undo=True)
    pump(qapp)
    notice = qml(root, "sheetNotice")
    notice.forceActiveFocus()
    pump(qapp)
    assert not bridge.sheets._timer.isActive()

    bridge.sheets._say("Second sheet notice", undo=True)
    pump(qapp)
    assert not bridge.sheets._timer.isActive()

    root.forceActiveFocus()
    pump(qapp)
    assert bridge.sheets._timer.isActive()
    assert bridge.sheets._timer.remainingTime() > 8000
    bridge.sheets.dismissNotice()


def test_a_notice_shown_again_under_a_still_pointer_waits(qapp: QApplication, window: NativeWindow) -> None:
    """Hover a notice, dismiss it, show the next without moving the pointer: it must not count down."""
    root = fresh_material(qapp, window)
    quick = window._material_page._quick
    sheets = window._material_page.bridge.sheets
    sheets._say("Hover old", undo=True)
    pump(qapp, 10)
    notice = qml(root, "sheetNotice")
    centre = notice.mapToScene(QPointF(notice.property("width") / 2, notice.property("height") / 2))
    QTest.mouseMove(quick, QPoint(int(centre.x()), int(centre.y())))
    pump(qapp, 10)
    assert notice.property("pointerHovered") is True
    assert not sheets._timer.isActive()
    sheets.dismissNotice()
    pump(qapp, 10)
    sheets._say("New without moving the pointer", undo=True)
    pump(qapp, 10)
    assert notice.property("visible") is True
    # Qt tells the notice the pointer is still over it on the next frame, not in the same turn, and a
    # busy machine takes longer to get there. The hold has to come, not come within ten event turns.
    wait_until(
        qapp,
        lambda: not sheets._timer.isActive(),
        what="a hovered notice is counting down",
    )
    QTest.mouseMove(quick, QPoint(2, 2))
    pump(qapp, 10)
    assert sheets._timer.isActive()
    assert sheets._timer.remainingTime() > bridge_sheets_module.NOTICE_MS - 1000
    sheets.dismissNotice()
