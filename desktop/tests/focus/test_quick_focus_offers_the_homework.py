"""Quick focus names the homework that is on now, or the next one today, and a session started there counts
toward it; "Just a timer" starts one that is tied to nothing, and with no homework left today the screen is
the plain timer it was. Both looks. The week is Thursday 19:10 with the History essay at 19:00 for an hour.
Expected values come from the decision, not from what the screen draws."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.focus_screen import READY
from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    focus_window,
    material_focus_window,
    on_screen,
    run_out,
    settled,
    visible_buttons,
)
from desktop.tests.material_support import pump, qml, show_material
from desktop.tests.window_support import qapp  # noqa: F401

WORK_MIN = 30


def essay_block(window: NativeWindow) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == "essay")


def move_essay(qapp: QApplication, window: NativeWindow, start: str) -> None:
    window.session.add_block({**essay_block(window), "start": start})
    window.session.save()
    settled(qapp, window)


def focus_minutes(window: NativeWindow) -> int:
    return int(window.session.assignments["essay"].get("focus_minutes") or 0)


def ready_screen(window: NativeWindow):
    window._open_focus_screen()
    assert on_screen(window) == "focusPage"
    assert window.session.focus is None
    return window.focus_screen


# --- the plain look ---------------------------------------------------------------------------------


def test_with_homework_on_now_the_screen_names_it_and_a_finished_session_counts_toward_it(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    screen = ready_screen(window)
    assert screen.phase.text() == READY
    assert screen.task.text() == "History essay"
    assert visible_buttons(screen) == ["Back", "Start", "Just a timer"]
    assert focus_minutes(window) == 0
    QTest.mouseClick(screen.start, Qt.MouseButton.LeftButton)
    assert window.session.focus["assignmentId"] == "essay"
    run_out(qapp, window)
    assert focus_minutes(window) == WORK_MIN, "the finished session added its time to the essay"


def test_with_homework_later_today_the_screen_names_the_next_one(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    move_essay(qapp, window, "21:00")
    screen = ready_screen(window)
    assert screen.task.text() == "History essay"
    assert visible_buttons(screen) == ["Back", "Start", "Just a timer"]
    QTest.mouseClick(screen.start, Qt.MouseButton.LeftButton)
    assert window.session.focus["assignmentId"] == "essay"
    run_out(qapp, window)
    assert focus_minutes(window) == WORK_MIN


def test_just_a_timer_starts_one_that_counts_toward_nothing(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    screen = ready_screen(window)
    QTest.mouseClick(screen.just_timer, Qt.MouseButton.LeftButton)
    focus = window.session.focus
    assert focus["title"] == "Quick focus" and not focus.get("assignmentId")
    run_out(qapp, window)
    assert focus_minutes(window) == 0


def test_with_no_homework_left_today_it_is_the_plain_timer(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    move_essay(qapp, window, "08:00")
    screen = ready_screen(window)
    assert screen.task.text() == "Quick focus"
    assert visible_buttons(screen) == ["Back", "Start"]
    QTest.mouseClick(screen.start, Qt.MouseButton.LeftButton)
    assert window.session.focus["title"] == "Quick focus"
    assert not window.session.focus.get("assignmentId")


def test_finished_homework_is_not_offered(qapp: QApplication, focus_window: NativeWindow) -> None:
    window = focus_window
    window.session.complete_homework("essay", True)
    screen = ready_screen(window)
    assert screen.task.text() == "Quick focus"
    assert visible_buttons(screen) == ["Back", "Start"]


def test_the_two_choices_are_reached_by_tab_and_work_with_enter_and_space(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    screen = ready_screen(window)
    screen.start.setFocus()
    QTest.keyClick(screen.start, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is screen.just_timer, "Tab goes from Start to Just a timer"
    QTest.keyClick(screen.just_timer, Qt.Key.Key_Return)
    assert window.session.focus is not None and not window.session.focus.get("assignmentId")
    window.session.reset_focus()
    screen = ready_screen(window)
    QTest.keyClick(screen.start, Qt.Key.Key_Space)
    assert window.session.focus["assignmentId"] == "essay"


def test_escape_goes_back_from_the_screen_with_a_choice_on_it(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    screen = ready_screen(window)
    screen.just_timer.setFocus()
    QTest.keyClick(screen.just_timer, Qt.Key.Key_Escape)
    assert on_screen(window) == "weekPage"
    assert window.session.focus is None


# --- Material ---------------------------------------------------------------------------------------


def material_with_essay(
    qapp: QApplication, window: NativeWindow, start: str = "19:00"
) -> tuple[QObject, QObject]:
    """The essay placed at `start` on Thursday, the clock at 19:10, and Material's Focus screen open ready."""
    from datetime import datetime, timedelta

    from backend.tests.fake_clock import CLOCK
    from desktop.native.calendar import sunday_due

    session = window.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19, minutes=10))
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    session.add_block({**essay_block(window), "start": start, "days": [3], "pinned": True})
    session.save()
    settled(qapp, window)
    root = show_material(qapp, window)
    window._open_focus_screen()
    pump(qapp)
    return root, window._material_page.bridge.focus


def text_of(root: QObject, name: str) -> str:
    return str(qml(root, name).property("text"))


@pytest.mark.parametrize("start", ["19:00", "21:00"])
def test_material_names_the_homework_on_now_or_next_and_start_counts_toward_it(
    qapp: QApplication, material_focus_window: NativeWindow, start: str
) -> None:
    window = material_focus_window
    root, focus = material_with_essay(qapp, window, start)
    assert text_of(root, "focusPhase") == "Ready when you are"
    assert text_of(root, "focusTitle") == "History essay"
    assert qml(root, "focusStart").property("visible") is True
    assert qml(root, "focusJustTimer").property("visible") is True
    focus.begin()
    pump(qapp)
    assert window.session.focus["assignmentId"] == "essay"
    run_out(qapp, window)
    assert focus_minutes(window) == WORK_MIN


def test_material_just_a_timer_counts_toward_nothing(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = material_with_essay(qapp, window)
    qml(root, "focusJustTimer").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    pump(qapp)
    assert window.session.focus["title"] == "Quick focus" and not window.session.focus.get("assignmentId")
    run_out(qapp, window)
    assert focus_minutes(window) == 0


def test_material_with_nothing_planned_today_is_the_plain_timer(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = material_with_essay(qapp, window, "08:00")
    assert text_of(root, "focusTitle") == "Quick focus"
    assert qml(root, "focusStart").property("visible") is True
    assert qml(root, "focusJustTimer").property("visible") is False
    focus.begin()
    pump(qapp)
    assert window.session.focus["title"] == "Quick focus" and not window.session.focus.get("assignmentId")


def test_material_tab_reaches_both_choices_and_space_starts_the_named_homework(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    root, focus = material_with_essay(qapp, window)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    qml(root, "focusStart").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    pump(qapp)
    assert scene.activeFocusItem().objectName() == "focusJustTimer"
    qml(root, "focusStart").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp)
    assert window.session.focus["assignmentId"] == "essay"
