"""Material's Focus screen against the real window and session: ready, start, pause, skip, finish, back,
and what the note says. Expected words and times are the app's and the spec's (a 30-minute default
focus, a 15-minute break, "Alerts muted", "Finish"), not read back from the QML file."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import ConfirmSheet
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


def test_back_leaves_a_running_timer_running_and_only_finish_asks(
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
    pump(qapp)
    assert asked == [] and not focus.open
    assert window.session.focus is not None and window.session.focus["phase"] == "work"
    window._open_focus_screen()
    pump(qapp)
    assert focus.open and window.session.focus["phase"] == "work"  # reopens on the same timer
    focus.finish()
    assert asked == [True]


def test_back_on_a_finished_session_clears_it_so_the_next_start_does_not_ask(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    """Back keeps a running timer, but a session that has finished has nothing to keep: Back clears it,
    so the next Start focus starts at once instead of asking to replace a timer that is over."""
    window = material_focus_window
    only = homework(qapp, window, "essay3", 1)[0]
    _root, focus = open_focus(qapp, window)
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    assert start(window, only)
    run_out(qapp, window)
    pump(qapp)
    assert window.session.focus["phase"] == "ended"
    focus.back()
    pump(qapp)
    assert asked == [] and not focus.open
    assert window.session.focus is None


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


def keep_on_replace(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every "Replace timer" question the window asks, answered Keep current timer (no modal wait)."""
    import desktop.native.window as window_module

    questions: list[str] = []

    class Keep:
        def __init__(
            self, _parent: object, _title: str, question: str, *_rest: object, **_options: object
        ) -> None:
            questions.append(question)
            self.answer = ""

        def exec(self) -> int:
            self.answer = "keep"
            return 0

    monkeypatch.setattr(window_module, "ConfirmSheet", Keep)
    return questions


def test_starting_the_homework_whose_timer_runs_opens_that_timer_without_asking(
    qapp: QApplication, material_focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "geography", 1)[0]
    show_material(qapp, window)
    focus = window._material_page.bridge.focus
    asked = keep_on_replace(monkeypatch)
    window.start_material_focus(only["id"], only["days"][0])
    pump(qapp)
    running = dict(window.session.focus)
    focus.hide()
    pump(qapp)
    window.start_material_focus(only["id"], only["days"][0])
    pump(qapp)
    assert asked == []
    assert focus.open
    assert window.session.focus == running
    focus.hide()
    assert window.session.start_focus("geography") is True  # the same homework, named by its id
    assert asked == [] and window.session.focus == running


def test_keep_current_timer_leaves_my_day_as_it_was_with_the_card_on_that_timer(
    qapp: QApplication, material_focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_focus_window
    first = homework(qapp, window, "biology", 1)[0]
    other = homework(qapp, window, "chemistry", 1)[0]
    questions = keep_on_replace(monkeypatch)
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    focus = bridge.focus
    window.start_material_focus(first["id"], first["days"][0])
    pump(qapp)
    running = dict(window.session.focus)
    focus.hide()
    bridge.showPage("myday")
    pump(qapp)
    window.start_material_focus(other["id"], other["days"][0])
    pump(qapp)
    assert questions == ["Stop the timer for Biology and start Chemistry instead?"]
    assert not focus.open
    assert bridge.screen == "myday"
    assert window.session.focus == running
    assert text_of(root, "myDayStartFocus") == "Back to Biology"
    assert text_of(root, "myDayNowTitle") == "Biology"


def _press_escape_on_the_replace_question(qapp: QApplication, seen: list[tuple[ConfirmSheet, bool]]) -> None:
    """The real keyboard path: Esc goes to the question's focused button. The question closed or not
    is noted in `seen`; one still open is answered Keep, so a failing test ends instead of hanging."""
    shown = [s for s in qapp.topLevelWidgets() if isinstance(s, ConfirmSheet) and s.isVisible()]
    if not shown:
        QTimer.singleShot(20, lambda: _press_escape_on_the_replace_question(qapp, seen))
        return
    sheet = shown[0]
    sheet.activateWindow()
    qapp.processEvents()
    QTest.keyClick(QApplication.focusWidget() or sheet, Qt.Key.Key_Escape)
    qapp.processEvents()
    seen.append((sheet, sheet.isVisible()))
    if sheet.isVisible():
        sheet.buttons["keep"].click()


def test_escape_closes_the_replace_timer_question_and_changes_nothing(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    first = homework(qapp, window, "physics", 1)[0]
    other = homework(qapp, window, "economics", 1)[0]
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    focus = bridge.focus
    seen: list[tuple[ConfirmSheet, bool]] = []
    window.start_material_focus(first["id"], first["days"][0])
    pump(qapp)
    running = dict(window.session.focus)
    focus.hide()
    bridge.showPage("myday")
    pump(qapp)
    QTimer.singleShot(20, lambda: _press_escape_on_the_replace_question(qapp, seen))
    window.start_material_focus(other["id"], other["days"][0])
    pump(qapp)
    assert len(seen) == 1
    sheet, still_open = seen[0]
    assert not still_open, "Esc left the Replace timer question open"
    assert sheet.answer in (None, "keep")
    assert window.session.focus == running
    assert not focus.open
    assert bridge.screen == "myday"
    assert text_of(root, "myDayStartFocus") == "Back to Physics"
    assert QApplication.focusWidget() is window._material_page._quick, "focus went back to the page"


def test_after_escape_closes_the_replace_timer_question_focus_is_back_on_the_button_that_opened_it(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    first = homework(qapp, window, "latin", 1)[0]
    other = homework(qapp, window, "greek", 1)[0]
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    focus = bridge.focus
    scene = window._material_page._quick.quickWindow()
    seen: list[tuple[ConfirmSheet, bool]] = []
    window.start_material_focus(first["id"], first["days"][0])
    pump(qapp)
    focus.hide()
    bridge.showPage("myday")
    pump(qapp)
    qml(root, "myDayStartFocus").forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem().objectName() == "myDayStartFocus"
    QTimer.singleShot(20, lambda: _press_escape_on_the_replace_question(qapp, seen))
    window.start_material_focus(other["id"], other["days"][0])
    pump(qapp)
    assert [still_open for _sheet, still_open in seen] == [False]
    assert scene.activeFocusItem() is not None
    assert scene.activeFocusItem().objectName() == "myDayStartFocus"
