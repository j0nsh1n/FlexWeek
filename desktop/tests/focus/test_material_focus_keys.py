"""Keys on Material's Focus screen: F opens it, Esc goes back (a running timer keeps running) or closes
the end question, Tab stays inside it, Enter and Space act on the layer in front, and the number keys
wait while it covers the window."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import material_focus_window  # noqa: F401
from desktop.tests.material_support import pump, qml, show_material
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def open_focus(qapp: QApplication, window: NativeWindow) -> tuple[QObject, QObject]:
    root = show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    return root, window._material_page.bridge.focus


def text_of(root: QObject, name: str) -> str:
    return str(qml(root, name).property("text"))


def test_the_number_keys_stay_put_while_focus_covers_the_window_and_work_after(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    bridge.showPage("week")
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_4)
    pump(qapp)
    assert bridge.property("screen") == "week"  # the 4 key is not My day's while Focus is up
    focus.hide()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_4)
    pump(qapp)
    assert bridge.property("screen") == "myday"


def test_f_opens_the_screen_from_day(qapp: QApplication, material_focus_window: NativeWindow) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    focus.hide()
    pump(qapp)
    # The letter keys start off; this student turned them on.
    look_file().write_text(json.dumps({"material": {"letters": True}}))
    window._material_page.publish()
    window._material_page.bridge.showPage("day")
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F)
    pump(qapp)
    assert focus.open
    assert qml(root, "materialFocus").property("visible") is True
    assert text_of(root, "focusPhase") == "Ready when you are"


def test_escape_on_the_screen_goes_back(qapp: QApplication, material_focus_window: NativeWindow) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    qml(root, "materialFocus").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert not focus.open  # nothing was running, so Back only closes


def test_escape_on_a_running_timer_goes_back_and_the_timer_keeps_running(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    focus.begin()
    qml(root, "materialFocus").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert asked == [] and qml(root, "focusEndDialog").property("open") is False
    assert not focus.open
    assert window.session.focus is not None and window.session.focus["phase"] == "work"


def test_escape_on_the_end_dialog_keeps_the_session_going(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    focus.begin()
    qml(root, "materialFocus").forceActiveFocus()
    pump(qapp)
    focus.finish()
    pump(qapp)
    dialog = qml(root, "focusEndDialog")
    assert asked == [True] and dialog.property("open") is True
    assert window.session.focus is not None and focus.open
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert dialog.property("open") is False
    assert window.session.focus is not None and focus.open


def _lineage(item: QObject | None) -> list[str]:
    out: list[str] = []
    while item is not None:
        out.append(item.objectName() or type(item).__name__)
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return out


def _tab_leaks(qapp: QApplication, quick, extra: str | None = None) -> list[tuple[int, list[str]]]:
    scene = quick.quickWindow()
    leaks: list[tuple[int, list[str]]] = []
    for index in range(12):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        pump(qapp, 3)
        chain = _lineage(scene.activeFocusItem())
        if "materialFocus" not in chain or (extra and extra not in chain):
            leaks.append((index + 1, chain))
        if "materialFab" in chain or "navWeek" in chain or "materialRail" in chain:
            leaks.append((index + 1, chain))
    return leaks


def test_focus_keeps_tab_inside_ready_running_paused_and_end(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    qml(root, "materialFocus").forceActiveFocus()
    pump(qapp)
    assert not _tab_leaks(qapp, quick)
    focus.begin()
    pump(qapp)
    qml(root, "focusPause").forceActiveFocus()
    pump(qapp)
    assert not _tab_leaks(qapp, quick)
    focus.togglePause()
    pump(qapp)
    qml(root, "focusPause").forceActiveFocus()
    pump(qapp)
    assert not _tab_leaks(qapp, quick)
    focus.togglePause()
    focus.finish()
    pump(qapp)
    dialog = qml(root, "focusEndDialog")
    assert dialog.property("open") is True
    qml(root, "dialogDismiss").forceActiveFocus()
    pump(qapp)
    assert not _tab_leaks(qapp, quick, extra="focusEndDialog")
    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp)
    assert dialog.property("open") is False
    assert focus.open
    focus.finish()
    pump(qapp)
    assert dialog.property("open") is True
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert dialog.property("open") is False
    focus.confirmEnd()
    pump(qapp)
    assert not focus.open
    qml(root, "navWeek").forceActiveFocus()
    pump(qapp)
    assert "navWeek" in _lineage(scene.activeFocusItem())


def _send_key(qapp: QApplication, item: QObject, key: Qt.Key) -> None:
    press = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    release = QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(item, press)
    qapp.sendEvent(item, release)
    pump(qapp)


def test_enter_and_space_on_focus_act_on_the_visible_layer(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    bridge = window._material_page.bridge
    start = qml(root, "focusStart")
    bridge.showPage("week")
    start.forceActiveFocus()
    pump(qapp)
    assert start.property("activeFocus") is True
    _send_key(qapp, start, Qt.Key.Key_Space)
    assert focus.open
    assert window.session.focus is not None
    assert window.session.focus["running"] is True
    assert bridge.property("screen") == "week"
    assert window._material_page.bridge.sheets.kind == ""
    pause = qml(root, "focusPause")
    pause.forceActiveFocus()
    pump(qapp)
    _send_key(qapp, pause, Qt.Key.Key_Return)
    assert window.session.focus["running"] is False
    assert bridge.property("screen") == "week"
    assert window._material_page.bridge.sheets.kind == ""
