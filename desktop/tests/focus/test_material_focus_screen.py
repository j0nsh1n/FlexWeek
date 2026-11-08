"""Material's Focus screen against the real window and session: ready, start, pause, skip, finish, back,
and what the note says. Expected words and times are the app's and the spec's (a 30-minute default
focus, a 15-minute break, "Alerts muted", "Finish"), not read back from the QML file."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    homework,
    material_focus_window,
    rules,
    run_out,
    settled,
    start,
)
from desktop.tests.material_support import pump, qml, show_material
from desktop.tests.window_support import qapp  # noqa: F401


def open_focus(qapp: QApplication, window: NativeWindow) -> tuple[QObject, QObject]:
    root = show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    return root, window._material_page.bridge.focus


def text_of(root: QObject, name: str) -> str:
    return str(qml(root, name).property("text"))


def test_the_screen_opens_ready_and_start_runs_the_sessions_own_30_minute_timer(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    assert focus.open and window._stack.currentWidget().objectName() == "materialPage"
    assert text_of(root, "focusPhase") == "Ready when you are"
    assert text_of(root, "focusTitle") == "Quick focus"
    assert text_of(root, "focusTime") == "30:00"
    assert qml(root, "focusStart").property("visible") is True
    assert qml(root, "focusPause").property("visible") is False
    focus.begin()
    pump(qapp)
    assert window.session.focus is not None  # the Widgets focus strip reads the same timer
    assert window.session.focus["phase"] == "work"
    assert text_of(root, "focusPhase") == "Focus"
    assert text_of(root, "focusTime") in ("30:00", "29:59")
    assert qml(root, "focusStart").property("visible") is False
    for name in ("focusSkip", "focusPause", "focusFinish"):
        assert qml(root, name).property("visible") is True


def test_the_screen_uses_the_presets_25_and_5_when_the_session_has_them(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    _root, focus = open_focus(qapp, window)
    session = window.session
    session.preferences = {**session.preferences, "timer_work_min": 25, "timer_break_min": 5}
    pump(qapp)
    focus.refresh()
    assert focus.timeText == "25:00"
    focus.begin()
    assert focus.timeText in ("25:00", "24:59")
    focus.skip()
    pump(qapp)
    assert focus.phaseText == "Break"
    assert focus.timeText in ("05:00", "04:59")


def test_pause_resume_and_skip_drive_the_session_and_say_so(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    focus.begin()
    assert text_of(root, "focusPause") == "Pause"
    focus.togglePause()
    pump(qapp)
    assert window.session.focus["running"] is False
    assert text_of(root, "focusPhase") == "Focus · Paused"
    assert text_of(root, "focusPause") == "Resume"
    focus.togglePause()
    assert window.session.focus["running"] is True
    focus.skip()
    pump(qapp)
    assert window.session.focus["phase"] == "break"
    assert text_of(root, "focusPhase") == "Break"
    focus.skip()
    assert window.session.focus["phase"] == "work"


def test_finish_asks_then_ends_the_session_and_leaves_the_screen(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    _root, focus = open_focus(qapp, window)
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    focus.begin()
    focus.finish()
    assert asked == [True]
    assert window.session.focus is not None  # nothing ends until the yes
    assert "min of Quick focus" in focus.endQuestion
    focus.confirmEnd()
    pump(qapp)
    assert window.session.focus is None
    assert not focus.open


def test_back_ends_a_running_session_the_same_way_and_a_ready_screen_just_closes(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    _root, focus = open_focus(qapp, window)
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    focus.back()
    assert not focus.open and asked == []  # ready: nothing to end
    window._open_focus_screen()
    focus.begin()
    focus.back()
    assert asked == [True] and window.session.focus is not None
    focus.confirmEnd()
    assert window.session.focus is None and not focus.open


def test_the_note_says_what_is_on_for_this_session(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = open_focus(qapp, window)
    session = window.session
    with rules(window, focus_audio="rain"):
        focus.begin()
        pump(qapp)
        assert text_of(root, "focusNote") == "Alerts muted · Rain"
        session.preferences = {**session.preferences, "focus_auto_mute": False, "focus_audio": "off"}
        focus.refresh()
        pump(qapp)
        assert text_of(root, "focusNote") == ""


def test_a_finished_session_offers_finished_for_open_homework_and_a_break(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "essay2", 1)[0]
    root, focus = open_focus(qapp, window)
    assert start(window, only)
    run_out(qapp, window)
    pump(qapp)
    assert window.session.focus["phase"] == "ended"
    assert text_of(root, "focusPhase") == "Session finished"
    assert qml(root, "focusFinished").property("visible") is True
    assert qml(root, "focusTakeBreak").property("visible") is True
    assert qml(root, "focusPause").property("visible") is False
    focus.markFinished()
    settled(qapp, window)
    assert window.session.assignments["essay2"]["completed"] is True
    assert not focus.open


def test_start_material_focus_opens_the_screen_on_that_homework(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "history", 1)[0]
    root = show_material(qapp, window)
    focus = window._material_page.bridge.focus
    window.start_material_focus(only["id"], only["days"][0])
    pump(qapp)
    assert focus.open
    assert text_of(root, "focusTitle") == "History"
    assert qml(root, "focusPause").property("visible") is True
    assert text_of(root, "focusPause") == "Pause"
